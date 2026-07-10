from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeTaskSubmitResponse(BaseModel):
    """
    提交知识库任务后的响应。
    """

    task_id: str = Field(..., description="任务 ID")
    status: str = Field(..., description="任务状态")
    message: str = Field(..., description="任务提交提示")


class KnowledgeTaskDetailResponse(BaseModel):
    """
    知识库任务详情响应。
    """

    task_id: str = Field(..., description="任务 ID")
    tenant_id: str = Field(..., description="租户 ID")
    user_id: str = Field(..., description="用户 ID")
    knowledge_base_id: str = Field(..., description="知识库 ID")
    task_type: str = Field(..., description="任务类型")
    status: str = Field(..., description="任务状态")
    progress: int = Field(..., description="任务进度，0-100")
    message: str | None = Field(default=None, description="任务状态描述")
    result: dict | None = Field(default=None, description="任务执行结果")
    error: str | None = Field(default=None, description="任务错误信息")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

class KnowledgeTaskListItem(BaseModel):
    task_id: str = Field(..., description="任务 ID")
    knowledge_base_id: str = Field(..., description="知识库 ID")
    task_type: str = Field(..., description="任务类型")
    status: str = Field(..., description="任务状态")
    progress: int = Field(..., description="任务进度，0-100")
    message: str | None = Field(default=None, description="任务状态描述")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class KnowledgeTaskListResponse(BaseModel):
    tasks: list[KnowledgeTaskListItem] = Field(default_factory=list)