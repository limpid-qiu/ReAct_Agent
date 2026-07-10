from sqlalchemy.orm import Session

from app.schemas.context import RequestContext
from app.schemas.rag import RagAnswerResponse
from rag.rag_service import RagSummarizeService
from rag.vector_store import VectorStoreService


class RagService:
    """
    RAG 业务服务。

    这一层负责封装知识库相关操作，让 API 层不要直接依赖底层向量库实现。
    """

    def __init__(self) -> None:
        """
        初始化 RAG 服务。

        当前版本直接创建 VectorStoreService 与 RagSummarizeService。
        后续企业级升级时，可以把它们替换为接口实现或依赖注入。
        """

        self.vector_store_service = VectorStoreService()
        self.rag_summarize_service = RagSummarizeService()

    def list_pending_files(
        self,
        db: Session,
        context: RequestContext,
    ) -> list[dict]:
        """
        查看待入库知识文件。
        """

        return self.vector_store_service.list_knowledge_files(
            db=db,
            context=context,
        )

    def rebuild_knowledge_base(
        self,
        db: Session,
        context: RequestContext,
    ) -> dict:
        """
        加载或重建知识库。

        当前底层方法是 VectorStoreService.load_document()。
        当前语义更接近增量加载：只加载数据库中不存在的新文件。
        """

        return self.vector_store_service.load_document(
            db=db,
            context=context,
        )

    def get_retriever(
        self,
        context: RequestContext,
    ):
        """
        获取带租户过滤条件的 retriever。
        """

        return self.vector_store_service.get_retriever(
            context=context,
        )

    def search(
        self,
        query: str,
        context: RequestContext,
    ) -> RagAnswerResponse:
        """
        执行一次结构化 RAG 检索与回答。

        返回 answer、citations 和 retrieved_chunks，方便前端展示引用来源，
        也方便后续构建 RAG 评估集。
        """

        return self.rag_summarize_service.rag_summarize_with_citations(
            query=query,
            context=context,
        )
    def ingest_document_version(
        self,
        db: Session,
        context: RequestContext,
        document_version_id: str,
        progress_callback=None,
    ) -> dict:
        """
        按文档版本执行入库。
        """

        return self.vector_store_service.ingest_document_version(
            db=db,
            context=context,
            document_version_id=document_version_id,
            progress_callback=progress_callback,
        )
    def soft_delete_document(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
    ) -> dict:
        """
        软删除文档，并从向量库移除相关向量。
        """

        return self.vector_store_service.soft_delete_document(
            db=db,
            context=context,
            document_id=document_id,
        )

    def rollback_document_version(
        self,
        db: Session,
        context: RequestContext,
        document_id: str,
        document_version_id: str,
    ) -> dict:
        """
        将文档回滚到指定版本。
        """

        return self.vector_store_service.rollback_document_version(
            db=db,
            context=context,
            document_id=document_id,
            document_version_id=document_version_id,
        )



