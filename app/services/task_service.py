from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeTask
from app.schemas.context import RequestContext
from app.schemas.task import (
    KnowledgeTaskDetailResponse,
    KnowledgeTaskListItem,
    KnowledgeTaskListResponse,
)


class TaskService:
    """
    任务服务。

    负责创建任务、更新任务状态、查询任务详情。
    """

    def create_knowledge_task(
        self,
        db: Session,
        context: RequestContext,
        task_type: str,
        message: str = "任务已提交",
    ) -> KnowledgeTask:
        task = KnowledgeTask(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            knowledge_base_id=context.knowledge_base_id or "default",
            task_type=task_type,
            status="pending",
            progress=0,
            message=message,
        )

        db.add(task)
        db.commit()
        db.refresh(task)

        return task

    def mark_running(
        self,
        db: Session,
        task_id: str,
        message: str = "任务执行中",
    ) -> None:
        task = db.get(KnowledgeTask, task_id)
        if not task:
            return

        task.status = "running"
        task.progress = 10
        task.message = message

        db.commit()


    def mark_progress(
        self,
        db: Session,
        task_id: str,
        progress: int,
        message: str,
        result: dict | None = None,
    ) -> None:
        task = db.get(KnowledgeTask, task_id)
        if not task:
            return

        task.status = "running"
        task.progress = max(0, min(progress, 99))
        task.message = message

        if result is not None:
            task.result = result

        db.commit()
    def mark_success(
        self,
        db: Session,
        task_id: str,
        result: dict,
        message: str = "任务执行成功",
    ) -> None:
        task = db.get(KnowledgeTask, task_id)
        if not task:
            return

        task.status = "success"
        task.progress = 100
        task.message = message
        task.result = result
        task.error = None

        db.commit()

    def mark_failed(
        self,
        db: Session,
        task_id: str,
        error: str,
        message: str = "任务执行失败",
    ) -> None:
        task = db.get(KnowledgeTask, task_id)
        if not task:
            return

        task.status = "failed"
        task.progress = 100
        task.message = message
        task.error = error

        db.commit()

    def get_knowledge_task(
        self,
        db: Session,
        context: RequestContext,
        task_id: str,
    ) -> KnowledgeTaskDetailResponse | None:
        task = db.scalar(
            select(KnowledgeTask).where(
                KnowledgeTask.id == task_id,
                KnowledgeTask.tenant_id == context.tenant_id,
                KnowledgeTask.user_id == context.user_id,
            )
        )

        if not task:
            return None

        return KnowledgeTaskDetailResponse(
            task_id=task.id,
            tenant_id=task.tenant_id,
            user_id=task.user_id,
            knowledge_base_id=task.knowledge_base_id,
            task_type=task.task_type,
            status=task.status,
            progress=task.progress,
            message=task.message,
            result=task.result,
            error=task.error,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
    
    def get_active_knowledge_task(
        self,
        db: Session,
        context: RequestContext,
        task_type: str,
    ) -> KnowledgeTask | None:
        return db.scalar(
            select(KnowledgeTask).where(
                KnowledgeTask.tenant_id == context.tenant_id,
                KnowledgeTask.user_id == context.user_id,
                KnowledgeTask.knowledge_base_id == (context.knowledge_base_id or "default"),
                KnowledgeTask.task_type == task_type,
                KnowledgeTask.status.in_(["pending", "running"]),
            )
        )
    
    def list_knowledge_tasks(
        self,
        db: Session,
        context: RequestContext,
        limit: int = 20,
        offset: int = 0,
    ) -> KnowledgeTaskListResponse:
        tasks = db.scalars(
            select(KnowledgeTask)
            .where(
                KnowledgeTask.tenant_id == context.tenant_id,
                KnowledgeTask.user_id == context.user_id,
                KnowledgeTask.knowledge_base_id == (context.knowledge_base_id or "default"),
            )
            .order_by(KnowledgeTask.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

        return KnowledgeTaskListResponse(
            tasks=[
                KnowledgeTaskListItem(
                    task_id=task.id,
                    knowledge_base_id=task.knowledge_base_id,
                    task_type=task.task_type,
                    status=task.status,
                    progress=task.progress,
                    message=task.message,
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                )
                for task in tasks
            ]
        )
