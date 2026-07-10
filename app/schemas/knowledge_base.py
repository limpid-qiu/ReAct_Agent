from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(..., description="知识库名称")
    description: str | None = Field(default=None, description="知识库描述")


class KnowledgeBaseItem(BaseModel):
    id: str = Field(..., description="知识库 ID")
    tenant_id: str = Field(..., description="租户 ID")
    name: str = Field(..., description="知识库名称")
    description: str | None = Field(default=None, description="知识库描述")
    created_by: str = Field(..., description="创建用户")
    status: str = Field(..., description="知识库状态")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class KnowledgeBaseCreateResponse(BaseModel):
    knowledge_base: KnowledgeBaseItem = Field(..., description="知识库信息")


class KnowledgeBaseListResponse(BaseModel):
    knowledge_bases: list[KnowledgeBaseItem] = Field(default_factory=list)