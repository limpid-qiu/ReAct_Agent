from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentVersion, KnowledgeChunk
from app.schemas.context import RequestContext
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentVersionItem,
    DocumentVersionListResponse,
    KnowledgeChunkItem,
    KnowledgeChunkListResponse,
)


class DocumentService:
    """
    文档服务。

    用 documents 表管理文件入库状态，替代 md5.txt。
    """

    @staticmethod
    def to_document_item(document: Document) -> DocumentListItem:
        return DocumentListItem(
            id=document.id,
            file_name=document.file_name,
            file_path=document.file_path,
            file_hash=document.file_hash,
            status=document.status,
            chunk_count=document.chunk_count,
            error=document.error,
            created_at=document.created_at,
            updated_at=document.updated_at,
            indexed_at=document.indexed_at,
        )

    @staticmethod
    def to_document_version_item(
        document_version: DocumentVersion,
    ) -> DocumentVersionItem:
        return DocumentVersionItem(
            id=document_version.id,
            document_id=document_version.document_id,
            version=document_version.version,
            file_name=document_version.file_name,
            file_path=document_version.file_path,
            file_hash=document_version.file_hash,
            status=document_version.status,
            is_active=document_version.is_active,
            chunk_count=document_version.chunk_count,
            error=document_version.error,
            created_by=document_version.created_by,
            created_at=document_version.created_at,
            parsed_at=document_version.parsed_at,
            indexed_at=document_version.indexed_at,
        )

    @staticmethod
    def to_knowledge_chunk_item(
        chunk: KnowledgeChunk,
    ) -> KnowledgeChunkItem:
        return KnowledgeChunkItem(
            id=chunk.id,
            tenant_id=chunk.tenant_id,
            knowledge_base_id=chunk.knowledge_base_id,
            document_id=chunk.document_id,
            document_version_id=chunk.document_version_id,
            chunk_index=chunk.chunk_index,
            chunk_hash=chunk.chunk_hash,
            content=chunk.content,
            source=chunk.source,
            page=chunk.page,
            vector_id=chunk.vector_id,
            metadata=chunk.metadata_,
            status=chunk.status,
            created_at=chunk.created_at,
        )

    def get_by_hash(
        self,
        db: Session,
        context: RequestContext,
        file_hash: str,
    ) -> Document | None:
        return db.scalar(
            select(Document).where(
                Document.tenant_id == context.tenant_id,
                Document.knowledge_base_id == (context.knowledge_base_id or "default"),
                Document.file_hash == file_hash,
                Document.status == "loaded",
            )
        )
    
    def get_by_file_name(
        self,
        db: Session,
        context: RequestContext,
        file_name: str,
    ) -> Document | None:
        return db.scalar(
            select(Document)
            .where(
                Document.tenant_id == context.tenant_id,
                Document.knowledge_base_id == (context.knowledge_base_id or "default"),
                Document.file_name == file_name,
                Document.status != "deleted",
            )
            .order_by(Document.created_at.desc())
        )

    def create_document(
        self,
        db: Session,
        context: RequestContext,
        file_name: str,
        file_path: str,
        file_hash: str,
        status: str = "pending",
    ) -> Document:
        document = Document(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            knowledge_base_id=context.knowledge_base_id or "default",
            file_name=file_name,
            file_path=file_path,
            file_hash=file_hash,
            status=status,
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        return document


    def create_uploaded_document(
        self,
        db: Session,
        context: RequestContext,
        file_name: str,
        file_path: str,
        file_hash: str,
    ) -> tuple[Document, DocumentVersion]:
        """
        创建上传文档及其初始版本。

        当前阶段只登记文档和版本，不立即解析、切片或写入向量库。
        后续后台任务会基于 document_version 执行入库流程。
        """

        document = self.get_by_file_name(
            db=db,
            context=context,
            file_name=file_name,
        )

        if document:
            document.file_path = file_path
            document.file_hash = file_hash
            document.status = "uploaded"
            document.error = None
            document.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(document)
        else:
            document = self.create_document(
                db=db,
                context=context,
                file_name=file_name,
                file_path=file_path,
                file_hash=file_hash,
                status="uploaded",
            )

        document_version = self.create_document_version(
            db=db,
            context=context,
            document=document,
            file_name=file_name,
            file_path=file_path,
            file_hash=file_hash,
            status="uploaded",
        )

        return document, document_version

    def mark_loaded(
        self,
        db: Session,
        document: Document,
        chunk_count: int,
    ) -> None:
        document.status = "loaded"
        document.chunk_count = chunk_count
        document.error = None
        document.indexed_at = datetime.utcnow()

        db.commit()

    def mark_skipped(
        self,
        db: Session,
        document: Document,
    ) -> None:
        document.status = "skipped"
        db.commit()

    def mark_failed(
        self,
        db: Session,
        document: Document,
        error: str,
    ) -> None:
        document.status = "failed"
        document.error = error
        db.commit()

    def mark_empty(
        self,
        db: Session,
        document: Document,
    ) -> None:
        document.status = "empty"
        db.commit()

    def list_documents(
        self,
        db: Session,
        context: RequestContext,
        limit: int = 20,
        offset: int = 0,
    ) -> DocumentListResponse:
        documents = db.scalars(
            select(Document)
            .where(
                Document.tenant_id == context.tenant_id,
                Document.knowledge_base_id == (context.knowledge_base_id or "default"),
            )
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

        return DocumentListResponse(
            documents=[
                self.to_document_item(document)
                for document in documents
            ]
        )
    
    def get_document(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
    ) -> Document | None:
        return db.scalar(
            select(Document).where(
                Document.id == document_id,
                Document.tenant_id == context.tenant_id,
                Document.knowledge_base_id == (context.knowledge_base_id or "default"),
            )
        )

    def get_latest_version_number(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
    ) -> int:
        latest_version = db.scalar(
            select(func.max(DocumentVersion.version)).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.tenant_id == context.tenant_id,
                DocumentVersion.knowledge_base_id == (context.knowledge_base_id or "default"),
            )
        )

        return latest_version or 0

    def create_document_version(
        self,
        db: Session,
        context: RequestContext,
        document: Document,
        file_name: str,
        file_path: str,
        file_hash: str,
        status: str = "pending",
    ) -> DocumentVersion:
        next_version = self.get_latest_version_number(
            db=db,
            context=context,
            document_id=document.id,
        ) + 1

        document_version = DocumentVersion(
            document_id=document.id,
            tenant_id=context.tenant_id,
            knowledge_base_id=context.knowledge_base_id or "default",
            version=next_version,
            file_name=file_name,
            file_path=file_path,
            file_hash=file_hash,
            status=status,
            is_active=False,
            chunk_count=0,
            created_by=context.user_id,
        )

        db.add(document_version)
        db.commit()
        db.refresh(document_version)

        return document_version


    def get_document_version(
        self,
        db: Session,
        context: RequestContext,
        document_version_id: str,
    ) -> DocumentVersion | None:
        return db.scalar(
            select(DocumentVersion).where(
                DocumentVersion.id == document_version_id,
                DocumentVersion.tenant_id == context.tenant_id,
                DocumentVersion.knowledge_base_id == (context.knowledge_base_id or "default"),
            )
        )

    def get_active_document_version(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
    ) -> DocumentVersion | None:
        return db.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.tenant_id == context.tenant_id,
                DocumentVersion.knowledge_base_id == (context.knowledge_base_id or "default"),
                DocumentVersion.is_active.is_(True),
            )
        )


    def list_active_document_versions(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
        exclude_version_id: str | None = None,
    ) -> list[DocumentVersion]:
        query = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.tenant_id == context.tenant_id,
            DocumentVersion.knowledge_base_id == (context.knowledge_base_id or "default"),
            DocumentVersion.is_active.is_(True),
        )

        if exclude_version_id:
            query = query.where(DocumentVersion.id != exclude_version_id)

        return list(db.scalars(query).all())

    def list_chunk_vector_ids(
        self,
        db: Session,
        context: RequestContext,
        document_version_ids: list[str],
    ) -> list[str]:
        if not document_version_ids:
            return []

        chunks = db.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.tenant_id == context.tenant_id,
                KnowledgeChunk.knowledge_base_id == (context.knowledge_base_id or "default"),
                KnowledgeChunk.document_version_id.in_(document_version_ids),
                KnowledgeChunk.vector_id.is_not(None),
            )
        ).all()

        return [
            chunk.vector_id
            for chunk in chunks
            if chunk.vector_id
        ]

    def deactivate_document_versions(
        self,
        db: Session,
        context: RequestContext,
        document_version_ids: list[str],
    ) -> None:
        if not document_version_ids:
            return

        versions = db.scalars(
            select(DocumentVersion).where(
                DocumentVersion.tenant_id == context.tenant_id,
                DocumentVersion.knowledge_base_id == (context.knowledge_base_id or "default"),
                DocumentVersion.id.in_(document_version_ids),
            )
        ).all()

        for version in versions:
            version.is_active = False
            if version.status == "active":
                version.status = "inactive"

        chunks = db.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.tenant_id == context.tenant_id,
                KnowledgeChunk.knowledge_base_id == (context.knowledge_base_id or "default"),
                KnowledgeChunk.document_version_id.in_(document_version_ids),
                KnowledgeChunk.status == "active",
            )
        ).all()

        for chunk in chunks:
            chunk.status = "inactive"
            if chunk.metadata_:
                chunk.metadata_ = {
                    **chunk.metadata_,
                    "status": "inactive",
                }

        db.commit()

    def list_document_versions(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
    ) -> list[DocumentVersion]:
        return list(
            db.scalars(
                select(DocumentVersion)
                .where(
                    DocumentVersion.document_id == document_id,
                    DocumentVersion.tenant_id == context.tenant_id,
                    DocumentVersion.knowledge_base_id == (context.knowledge_base_id or "default"),
                )
                .order_by(DocumentVersion.version.desc())
            ).all()
        )

    def mark_version_parsed(
        self,
        db: Session,
        document_version: DocumentVersion,
    ) -> None:
        document_version.status = "parsed"
        document_version.parsed_at = datetime.utcnow()

        db.commit()

    def mark_version_indexed(
        self,
        db: Session,
        document_version: DocumentVersion,
        chunk_count: int,
    ) -> None:
        document_version.status = "indexed"
        document_version.chunk_count = chunk_count
        document_version.indexed_at = datetime.utcnow()
        document_version.error = None

        db.commit()

    def mark_version_failed(
        self,
        db: Session,
        document_version: DocumentVersion,
        error: str,
    ) -> None:
        document_version.status = "failed"
        document_version.error = error

        db.commit()

    def activate_document_version(
        self,
        db: Session,
        context: RequestContext,
        document: Document,
        document_version: DocumentVersion,
    ) -> None:
        old_versions = db.scalars(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.tenant_id == context.tenant_id,
                DocumentVersion.knowledge_base_id == (context.knowledge_base_id or "default"),
                DocumentVersion.is_active.is_(True),
            )
        ).all()

        for old_version in old_versions:
            old_version.is_active = False

        document_version.is_active = True
        document_version.status = "active"

        document.file_name = document_version.file_name
        document.file_path = document_version.file_path
        document.file_hash = document_version.file_hash
        document.status = "loaded"
        document.chunk_count = document_version.chunk_count
        document.error = None
        document.indexed_at = document_version.indexed_at or datetime.utcnow()

        db.commit()

    def create_knowledge_chunks(
        self,
        db: Session,
        context: RequestContext,
        document: Document,
        document_version: DocumentVersion,
        chunks: list[dict],
    ) -> list[KnowledgeChunk]:
        knowledge_chunks = []

        for chunk in chunks:
            knowledge_chunk = KnowledgeChunk(
                tenant_id=context.tenant_id,
                knowledge_base_id=context.knowledge_base_id or "default",
                document_id=document.id,
                document_version_id=document_version.id,
                chunk_index=chunk["chunk_index"],
                chunk_hash=chunk["chunk_hash"],
                content=chunk["content"],
                source=chunk.get("source"),
                page=chunk.get("page"),
                vector_id=chunk.get("vector_id"),
                metadata_=chunk.get("metadata"),
                status=chunk.get("status", "active"),
            )
            knowledge_chunks.append(knowledge_chunk)

        db.add_all(knowledge_chunks)
        db.commit()

        for knowledge_chunk in knowledge_chunks:
            db.refresh(knowledge_chunk)

        return knowledge_chunks

    def list_document_chunks(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
        document_version_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[KnowledgeChunk]:
        query = select(KnowledgeChunk).where(
            KnowledgeChunk.document_id == document_id,
            KnowledgeChunk.tenant_id == context.tenant_id,
            KnowledgeChunk.knowledge_base_id == (context.knowledge_base_id or "default"),
        )

        if document_version_id:
            query = query.where(
                KnowledgeChunk.document_version_id == document_version_id,
            )

        return list(
            db.scalars(
                query
                .order_by(KnowledgeChunk.chunk_index.asc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
    

    def soft_delete_document(
        self,
        db: Session,
        context: RequestContext,
        document: Document,
    ) -> None:
        versions = db.scalars(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.tenant_id == context.tenant_id,
                DocumentVersion.knowledge_base_id == (context.knowledge_base_id or "default"),
            )
        ).all()

        for version in versions:
            version.is_active = False
            version.status = "deleted"

        chunks = db.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.document_id == document.id,
                KnowledgeChunk.tenant_id == context.tenant_id,
                KnowledgeChunk.knowledge_base_id == (context.knowledge_base_id or "default"),
            )
        ).all()

        for chunk in chunks:
            chunk.status = "deleted"
            if chunk.metadata_:
                chunk.metadata_ = {
                    **chunk.metadata_,
                    "status": "deleted",
                }

        document.status = "deleted"
        document.error = None
        db.commit()

    def activate_document_version_chunks(
        self,
        db: Session,
        context: RequestContext,
        document_version: DocumentVersion,
    ) -> None:
        chunks = db.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.tenant_id == context.tenant_id,
                KnowledgeChunk.knowledge_base_id == (context.knowledge_base_id or "default"),
                KnowledgeChunk.document_version_id == document_version.id,
            )
        ).all()

        for chunk in chunks:
            chunk.status = "active"
            if chunk.metadata_:
                chunk.metadata_ = {
                    **chunk.metadata_,
                    "status": "active",
                }

        db.commit()

    def list_version_chunks(
        self,
        db: Session,
        context: RequestContext,
        document_version_id: str,
    ) -> list[KnowledgeChunk]:
        return list(
            db.scalars(
                select(KnowledgeChunk)
                .where(
                    KnowledgeChunk.tenant_id == context.tenant_id,
                    KnowledgeChunk.knowledge_base_id == (context.knowledge_base_id or "default"),
                    KnowledgeChunk.document_version_id == document_version_id,
                )
                .order_by(KnowledgeChunk.chunk_index.asc())
            ).all()
        )
    def get_document_detail(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
    ) -> DocumentDetailResponse | None:
        document = self.get_document(
            db=db,
            context=context,
            document_id=document_id,
        )

        if not document:
            return None

        active_version = self.get_active_document_version(
            db=db,
            context=context,
            document_id=document.id,
        )

        return DocumentDetailResponse(
            document=self.to_document_item(document),
            active_version=(
                self.to_document_version_item(active_version)
                if active_version
                else None
            ),
        )

    def list_document_version_items(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
    ) -> DocumentVersionListResponse | None:
        document = self.get_document(
            db=db,
            context=context,
            document_id=document_id,
        )

        if not document:
            return None

        versions = self.list_document_versions(
            db=db,
            context=context,
            document_id=document_id,
        )

        return DocumentVersionListResponse(
            versions=[
                self.to_document_version_item(version)
                for version in versions
            ]
        )

    def list_document_chunk_items(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
        document_version_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> KnowledgeChunkListResponse | None:
        document = self.get_document(
            db=db,
            context=context,
            document_id=document_id,
        )

        if not document:
            return None

        chunks = self.list_document_chunks(
            db=db,
            context=context,
            document_id=document_id,
            document_version_id=document_version_id,
            limit=limit,
            offset=offset,
        )

        return KnowledgeChunkListResponse(
            chunks=[
                self.to_knowledge_chunk_item(chunk)
                for chunk in chunks
            ]
        )




