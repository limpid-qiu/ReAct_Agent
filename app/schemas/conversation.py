from datetime import datetime

from pydantic import BaseModel, Field


class MessageItem(BaseModel):
    id: str = Field(..., description="消息 ID")
    role: str = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    created_at: datetime = Field(..., description="创建时间")


class ConversationDetailResponse(BaseModel):
    id: str = Field(..., description="会话 ID")
    tenant_id: str = Field(..., description="租户 ID")
    user_id: str = Field(..., description="用户 ID")
    title: str | None = Field(default=None, description="会话标题")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    messages: list[MessageItem] = Field(default_factory=list)

class ConversationListItem(BaseModel):
    id: str = Field(..., description="会话 ID")
    title: str | None = Field(default=None, description="会话标题")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    message_count: int = Field(default=0, description="消息数量")


class ConversationListResponse(BaseModel):
    conversations: list[ConversationListItem] = Field(default_factory=list)