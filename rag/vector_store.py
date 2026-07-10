import hashlib
import os

from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LangChainDocument
from utils.config_handler import chroma_config
from model.factory import embedding_model
from utils.file_handler import docx_loader, listdir_with_allowed_types,get_file_md5_hex, pdf_loader, text_loader
from utils.logger_handler import logger
from app.schemas.context import RequestContext
from sqlalchemy.orm import Session
from app.services.document_service import DocumentService


class VectorStoreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name=chroma_config["collection_name"],
            embedding_function=embedding_model,
            persist_directory=chroma_config["persist_directory"]
        )

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_config["chunk_size"],
            chunk_overlap=chroma_config["chunk_overlap"],
            separators=chroma_config["separators"],
            length_function=len
        )

        self.document_service = DocumentService()

    def get_retriever(self, context: RequestContext):
        """
        获取带多租户过滤条件的 retriever。

        注意：
        所有 RAG 检索都必须带 tenant_id / knowledge_base_id filter，
        避免不同租户或知识库之间串数据。
        """

        return self.vector_store.as_retriever(
            search_kwargs={
                "k": chroma_config["k"],
                "filter": context.rag_filter(),
            }
        )
    
    @staticmethod
    def get_chunk_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def get_file_documents(file_path: str):
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".txt":
            return text_loader(file_path)
        if ext == ".pdf":
            return pdf_loader(file_path)
        if ext == ".docx":
            return docx_loader(file_path)
        return []

    @staticmethod
    def get_allowed_file_paths():
        """
        Get the list of allowed knowledge file paths.

        Returns:
            list: A list of allowed knowledge file paths.
        """
        return listdir_with_allowed_types(
            chroma_config.get("data_path", "data"),
            chroma_config.get("allow_knowledge_file_type", [])
        )
    
    @classmethod
    def list_knowledge_files(
        cls,
        db: Session,
        context: RequestContext,
    ):
        files = []

        document_service = DocumentService()

        for file_path in cls.get_allowed_file_paths():
            md5 = get_file_md5_hex(file_path)

            if not md5:
                files.append(
                    {
                        "name": os.path.basename(file_path),
                        "path": file_path,
                        "md5": md5,
                        "status": "failed",
                        "message": "文件读取失败",
                    }
                )
                continue

            existing = document_service.get_by_hash(
                db=db,
                context=context,
                file_hash=md5,
            )

            if existing:
                continue

            files.append(
                {
                    "name": os.path.basename(file_path),
                    "path": file_path,
                    "md5": md5,
                    "status": "pending",
                    "message": "待入库",
                }
            )

        files.sort(key=lambda x: x["name"])
        return files
    



    @staticmethod
    def _emit_progress(progress_callback, progress: int, message: str, result: dict | None = None) -> None:
        if progress_callback:
            progress_callback(progress, message, result)
    def delete_vectors(self, vector_ids: list[str]) -> None:
        if not vector_ids:
            return

        self.vector_store.delete(ids=vector_ids)

    def deactivate_previous_versions(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
        current_version_id: str,
    ) -> dict:
        old_versions = self.document_service.list_active_document_versions(
            db=db,
            context=context,
            document_id=document_id,
            exclude_version_id=current_version_id,
        )
        old_version_ids = [version.id for version in old_versions]
        old_vector_ids = self.document_service.list_chunk_vector_ids(
            db=db,
            context=context,
            document_version_ids=old_version_ids,
        )

        self.delete_vectors(old_vector_ids)
        self.document_service.deactivate_document_versions(
            db=db,
            context=context,
            document_version_ids=old_version_ids,
        )

        return {
            "deactivated_versions": len(old_version_ids),
            "deleted_vectors": len(old_vector_ids),
        }

    def soft_delete_document(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
    ) -> dict:
        document = self.document_service.get_document(
            db=db,
            context=context,
            document_id=document_id,
        )

        if not document:
            raise ValueError("文档不存在或无权访问")

        versions = self.document_service.list_document_versions(
            db=db,
            context=context,
            document_id=document.id,
        )
        version_ids = [version.id for version in versions]
        vector_ids = self.document_service.list_chunk_vector_ids(
            db=db,
            context=context,
            document_version_ids=version_ids,
        )

        self.delete_vectors(vector_ids)
        self.document_service.soft_delete_document(
            db=db,
            context=context,
            document=document,
        )

        return {
            "document_id": document.id,
            "deleted_versions": len(version_ids),
            "deleted_vectors": len(vector_ids),
        }

    def restore_document_version_vectors(
        self,
        db: Session,
        context: RequestContext,
        document_version_id: str,
    ) -> int:
        chunks = self.document_service.list_version_chunks(
            db=db,
            context=context,
            document_version_id=document_version_id,
        )

        if not chunks:
            raise ValueError("目标版本没有可恢复的 chunk")

        documents = []
        vector_ids = []
        for chunk in chunks:
            metadata = {
                **(chunk.metadata_ or {}),
                "tenant_id": chunk.tenant_id,
                "knowledge_base_id": chunk.knowledge_base_id,
                "document_id": chunk.document_id,
                "document_version_id": chunk.document_version_id,
                "chunk_id": chunk.vector_id or chunk.id,
                "chunk_index": chunk.chunk_index,
                "chunk_hash": chunk.chunk_hash,
                "source": chunk.source,
                "status": "active",
            }
            documents.append(
                LangChainDocument(
                    page_content=chunk.content,
                    metadata=metadata,
                )
            )
            vector_ids.append(chunk.vector_id or chunk.id)

        self.vector_store.add_documents(
            documents,
            ids=vector_ids,
        )

        return len(documents)

    def rollback_document_version(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
        document_version_id: str,
    ) -> dict:
        document = self.document_service.get_document(
            db=db,
            context=context,
            document_id=document_id,
        )
        if not document:
            raise ValueError("文档不存在或无权访问")

        target_version = self.document_service.get_document_version(
            db=db,
            context=context,
            document_version_id=document_version_id,
        )
        if not target_version or target_version.document_id != document.id:
            raise ValueError("目标版本不存在或无权访问")

        cleanup_stats = self.deactivate_previous_versions(
            db=db,
            context=context,
            document_id=document.id,
            current_version_id=target_version.id,
        )
        restored_vectors = self.restore_document_version_vectors(
            db=db,
            context=context,
            document_version_id=target_version.id,
        )
        self.document_service.activate_document_version_chunks(
            db=db,
            context=context,
            document_version=target_version,
        )
        self.document_service.activate_document_version(
            db=db,
            context=context,
            document=document,
            document_version=target_version,
        )

        return {
            "document_id": document.id,
            "document_version_id": target_version.id,
            "restored_vectors": restored_vectors,
            **cleanup_stats,
        }

    def ingest_document_version(
        self,
        db: Session,
        context: RequestContext,
        document_version_id: str,
        progress_callback=None,
    ) -> dict:
        """
        按单个 document_version 执行解析、切片、向量入库和 chunk 落库。

        这是上传文件后的后台入库入口，不再扫描整个 data 目录。
        """

        self._emit_progress(progress_callback, 10, "校验文档版本")

        document_version = self.document_service.get_document_version(
            db=db,
            context=context,
            document_version_id=document_version_id,
        )

        if not document_version:
            raise ValueError("文档版本不存在或无权访问")

        document = self.document_service.get_document(
            db=db,
            context=context,
            document_id=document_version.document_id,
        )

        if not document:
            raise ValueError("文档不存在或无权访问")

        stats = {
            "document_id": document.id,
            "document_version_id": document_version.id,
            "file_name": document_version.file_name,
            "file_path": document_version.file_path,
            "chunks": 0,
            "status": "running",
        }

        try:
            document.status = "indexing"
            document.error = None
            document_version.status = "indexing"
            document_version.error = None
            db.commit()

            self._emit_progress(progress_callback, 20, "文档解析中", stats)
            documents = self.get_file_documents(document_version.file_path)
            if not documents:
                self.document_service.mark_empty(
                    db=db,
                    document=document,
                )
                self.document_service.mark_version_failed(
                    db=db,
                    document_version=document_version,
                    error="文件内容为空",
                )
                stats["status"] = "empty"
                stats["message"] = "文件内容为空"
                return stats

            self._emit_progress(progress_callback, 40, "文档切片中", stats)
            chunks = self.splitter.split_documents(documents)
            if not chunks:
                self.document_service.mark_empty(
                    db=db,
                    document=document,
                )
                self.document_service.mark_version_failed(
                    db=db,
                    document_version=document_version,
                    error="文件切片为空",
                )
                stats["status"] = "empty"
                stats["message"] = "文件切片为空"
                return stats

            self.document_service.mark_version_parsed(
                db=db,
                document_version=document_version,
            )

            knowledge_base_id = context.knowledge_base_id or "default"
            vector_ids = []
            chunk_records = []

            for index, chunk in enumerate(chunks):
                chunk_id = f"{document_version.id}_chunk_{index}"
                chunk_hash = self.get_chunk_hash(chunk.page_content)
                source = chunk.metadata.get("source") or document_version.file_path
                page = chunk.metadata.get("page")

                vector_ids.append(chunk_id)

                chunk.metadata = {
                    **chunk.metadata,
                    "tenant_id": context.tenant_id,
                    "knowledge_base_id": knowledge_base_id,
                    "document_id": document.id,
                    "document_version_id": document_version.id,
                    "document_version": document_version.version,
                    "chunk_id": chunk_id,
                    "chunk_index": index,
                    "chunk_hash": chunk_hash,
                    "source": source,
                    "status": "active",
                }

                chunk_records.append(
                    {
                        "chunk_index": index,
                        "chunk_hash": chunk_hash,
                        "content": chunk.page_content,
                        "source": source,
                        "page": str(page) if page is not None else None,
                        "vector_id": chunk_id,
                        "metadata": chunk.metadata,
                        "status": "active",
                    }
                )

            self._emit_progress(
                progress_callback,
                60,
                "向量写入中",
                {**stats, "chunks": len(chunks)},
            )

            self.vector_store.add_documents(
                chunks,
                ids=vector_ids,
            )

            self._emit_progress(
                progress_callback,
                80,
                "chunk 元数据写入中",
                {**stats, "chunks": len(chunks)},
            )

            self.document_service.create_knowledge_chunks(
                db=db,
                context=context,
                document=document,
                document_version=document_version,
                chunks=chunk_records,
            )

            self.document_service.mark_version_indexed(
                db=db,
                document_version=document_version,
                chunk_count=len(chunks),
            )

            cleanup_stats = self.deactivate_previous_versions(
                db=db,
                context=context,
                document_id=document.id,
                current_version_id=document_version.id,
            )

            self._emit_progress(
                progress_callback,
                90,
                "文档版本激活中",
                {**stats, "chunks": len(chunks), **cleanup_stats},
            )

            self.document_service.activate_document_version(
                db=db,
                context=context,
                document=document,
                document_version=document_version,
            )

            stats.update(cleanup_stats)
            stats["chunks"] = len(chunks)
            stats["status"] = "loaded"
            stats["message"] = "文档入库完成"
            logger.info(
                f"Ingested document_version {document_version.id} with {len(chunks)} chunks."
            )
            return stats

        except Exception as exc:
            self.document_service.mark_failed(
                db=db,
                document=document,
                error=str(exc),
            )
            self.document_service.mark_version_failed(
                db=db,
                document_version=document_version,
                error=str(exc),
            )
            logger.error(f"Failed to ingest document_version {document_version.id}: {exc}")
            raise
    def load_document(
        self,
        db: Session,
        context: RequestContext,
    ):
        stats = {
            "scanned": 0,
            "loaded": 0,
            "skipped": 0,
            "failed": 0,
            "empty": 0,
            "chunks": 0,
            "files": [],
        }

        def get_file_documents(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".txt":
                return text_loader(file_path)
            elif ext == ".pdf":
                return pdf_loader(file_path)
            elif ext == ".docx":
                return docx_loader(file_path)
            else:
                return []
            
        for file_path in self.get_allowed_file_paths():
            stats["scanned"] += 1

            file_result = {
                "name": os.path.basename(file_path),
                "path": file_path,
                "status": "pending",
                "message": "待处理",
                "chunks": 0,
            }
            md5_hex = get_file_md5_hex(file_path)
            file_result["md5"] = md5_hex

            if not md5_hex:
                stats["failed"] += 1
                file_result["status"] = "failed"
                file_result["message"] = "文件读取失败"
                stats["files"].append(file_result)
                continue

            existing_document = self.document_service.get_by_hash(
                db=db,
                context=context,
                file_hash=md5_hex,
            )

            if existing_document:
                stats["skipped"] += 1
                file_result["status"] = "skipped"
                file_result["message"] = "文件已存在"
                stats["files"].append(file_result)
                logger.info(
                    f"Skipped file {file_path} (MD5: {md5_hex}) - already exists for tenant/kb."
                )
                continue

            document_record = self.document_service.create_document(
                db=db,
                context=context,
                file_name=os.path.basename(file_path),
                file_path=file_path,
                file_hash=md5_hex,
                status="pending",
            )

            document_version = self.document_service.create_document_version(
                db=db,
                context=context,
                document=document_record,
                file_name=os.path.basename(file_path),
                file_path=file_path,
                file_hash=md5_hex,
                status="pending",
            )

            try:
                documents = get_file_documents(file_path)
                if not documents:
                    stats["empty"] += 1
                    file_result["status"] = "empty"
                    file_result["message"] = "文件内容为空"
                    stats["files"].append(file_result)
                    self.document_service.mark_empty(
                        db=db,
                        document=document_record,
                    )
                    self.document_service.mark_version_failed(
                        db=db,
                        document_version=document_version,
                        error="文件内容为空",
                    )
                    logger.warning(f"File {file_path} (MD5: {md5_hex}) is empty.")
                    continue

                chunks = self.splitter.split_documents(documents)
                if not chunks:
                    stats["empty"] += 1
                    file_result["status"] = "empty"
                    file_result["message"] = "文件内容为空"
                    stats["files"].append(file_result)
                    self.document_service.mark_empty(
                        db=db,
                        document=document_record,
                    )
                    self.document_service.mark_version_failed(
                        db=db,
                        document_version=document_version,
                        error="文件内容为空",
                    )
                    logger.warning(f"File {file_path} (MD5: {md5_hex}) has no chunks after splitting.")
                    continue

                self.document_service.mark_version_parsed(
                    db=db,
                    document_version=document_version,
                )

                document_id = document_record.id
                knowledge_base_id = context.knowledge_base_id or "default"

                vector_ids = []
                chunk_records = []

                for index, chunk in enumerate(chunks):
                    chunk_id = f"{document_version.id}_chunk_{index}"
                    chunk_hash = self.get_chunk_hash(chunk.page_content)
                    source = chunk.metadata.get("source") or file_path
                    page = chunk.metadata.get("page")

                    vector_ids.append(chunk_id)

                    chunk.metadata = {
                        **chunk.metadata,
                        "tenant_id": context.tenant_id,
                        "knowledge_base_id": knowledge_base_id,
                        "document_id": document_id,
                        "document_version_id": document_version.id,
                        "document_version": document_version.version,
                        "chunk_id": chunk_id,
                        "chunk_index": index,
                        "chunk_hash": chunk_hash,
                        "source": source,
                        "status": "active",
                    }

                    chunk_records.append(
                        {
                            "chunk_index": index,
                            "chunk_hash": chunk_hash,
                            "content": chunk.page_content,
                            "source": source,
                            "page": str(page) if page is not None else None,
                            "vector_id": chunk_id,
                            "metadata": chunk.metadata,
                            "status": "active",
                        }
                    )

                self.vector_store.add_documents(
                    chunks,
                    ids=vector_ids,
                )

                self.document_service.create_knowledge_chunks(
                    db=db,
                    context=context,
                    document=document_record,
                    document_version=document_version,
                    chunks=chunk_records,
                )

                self.document_service.mark_version_indexed(
                    db=db,
                    document_version=document_version,
                    chunk_count=len(chunks),
                )

                self.document_service.activate_document_version(
                    db=db,
                    context=context,
                    document=document_record,
                    document_version=document_version,
                )

                stats["loaded"] += 1
                stats["chunks"] += len(chunks)
                file_result["status"] = "loaded"
                file_result["message"] = "文件已加载"
                file_result["chunks"] = len(chunks)
                stats["files"].append(file_result)
                logger.info(f"Loaded file {file_path} (MD5: {md5_hex}) with {len(chunks)} chunks.")

            except Exception as e:
                stats["failed"] += 1
                file_result["status"] = "failed"
                file_result["message"] = f"加载失败: {str(e)}"
                stats["files"].append(file_result)
                self.document_service.mark_failed(
                    db=db,
                    document=document_record,
                    error=str(e),
                )
                self.document_service.mark_version_failed(
                    db=db,
                    document_version=document_version,
                    error=str(e),
                )
                logger.error(f"Failed to load file {file_path} (MD5: {md5_hex}): {e}")
                continue

        knowledge_files = self.list_knowledge_files(
            db=db,
            context=context,
        )
        stats["knowledge_files"] = knowledge_files
        return stats