from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeBase
from app.schemas.context import RequestContext
from app.schemas.knowledge_base import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseCreateResponse,
    KnowledgeBaseItem,
    KnowledgeBaseListResponse,
)


class KnowledgeBaseService:
    """
    知识库服务。

    第三阶段新增：
    显式管理租户下的知识库资源。
    """

    @staticmethod
    def get_default_knowledge_base_id(tenant_id: str) -> str:
        return f"kb_default_{tenant_id}"
    @staticmethod
    def to_knowledge_base_item(
        knowledge_base: KnowledgeBase,
    ) -> KnowledgeBaseItem:
        return KnowledgeBaseItem(
            id=knowledge_base.id,
            tenant_id=knowledge_base.tenant_id,
            name=knowledge_base.name,
            description=knowledge_base.description,
            created_by=knowledge_base.created_by,
            status=knowledge_base.status,
            created_at=knowledge_base.created_at,
            updated_at=knowledge_base.updated_at,
        )

    def create_knowledge_base(
        self,
        db: Session,
        context: RequestContext,
        request: KnowledgeBaseCreateRequest,
    ) -> KnowledgeBaseCreateResponse:
        knowledge_base = KnowledgeBase(
            tenant_id=context.tenant_id,
            name=request.name,
            description=request.description,
            created_by=context.user_id,
            status="active",
        )

        db.add(knowledge_base)
        db.commit()
        db.refresh(knowledge_base)

        return KnowledgeBaseCreateResponse(
            knowledge_base=self.to_knowledge_base_item(knowledge_base),
        )

    def list_knowledge_bases(
        self,
        db: Session,
        context: RequestContext,
        limit: int = 20,
        offset: int = 0,
    ) -> KnowledgeBaseListResponse:
        knowledge_bases = db.scalars(
            select(KnowledgeBase)
            .where(
                KnowledgeBase.tenant_id == context.tenant_id,
                KnowledgeBase.status == "active",
            )
            .order_by(KnowledgeBase.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

        return KnowledgeBaseListResponse(
            knowledge_bases=[
                self.to_knowledge_base_item(knowledge_base)
                for knowledge_base in knowledge_bases
            ]
        )

    def get_knowledge_base(
        self,
        db: Session,
        context: RequestContext,
        knowledge_base_id: str,
    ) -> KnowledgeBase | None:
        return db.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.id == knowledge_base_id,
                KnowledgeBase.tenant_id == context.tenant_id,
                KnowledgeBase.status == "active",
            )
        )
    
    def get_or_create_default_knowledge_base(
        self,
        db: Session,
        context: RequestContext,
    ) -> KnowledgeBase:
        default_knowledge_base = db.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.tenant_id == context.tenant_id,
                KnowledgeBase.name == "default",
                KnowledgeBase.status == "active",
            )
        )

        if default_knowledge_base:
            return default_knowledge_base

        default_knowledge_base = KnowledgeBase(
            id=self.get_default_knowledge_base_id(context.tenant_id),
            tenant_id=context.tenant_id,
            name="default",
            description="默认知识库",
            created_by=context.user_id,
            status="active",
        )

        db.add(default_knowledge_base)
        db.commit()
        db.refresh(default_knowledge_base)

        return default_knowledge_base
    
    def resolve_knowledge_base(
        self,
        db: Session,
        context: RequestContext,
    ) -> KnowledgeBase | None:
        if not context.knowledge_base_id or context.knowledge_base_id == "default":
            return self.get_or_create_default_knowledge_base(
                db=db,
                context=context,
            )

        return self.get_knowledge_base(
            db=db,
            context=context,
            knowledge_base_id=context.knowledge_base_id,
        )
