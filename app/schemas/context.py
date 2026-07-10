from uuid import uuid4

from pydantic import BaseModel, Field


class RequestContext(BaseModel):
    """
    单次请求的业务上下文。

    这个对象会在 API 层解析出来，并继续传给：
    - ConversationService
    - AgentService
    - RagService
    - Tool 调用层
    - 日志 / 审计 / 限流模块

    目标：
    不让 user_id、tenant_id、knowledge_base_id 这些关键隔离字段散落在各处。
    """

    request_id: str = Field(
        ...,
        description="请求 ID，用于日志追踪和链路排查",
        examples=["req_01HYX9QK7M8N3P2A1B4C5D6E7F"],
    )

    user_id: str = Field(
        ...,
        description="用户 ID，用于用户级权限、限流、会话归属",
        examples=["user_001"],
    )

    tenant_id: str = Field(
        ...,
        description="租户 ID，用于多租户数据隔离",
        examples=["tenant_001"],
    )

    conversation_id: str | None = Field(
        default=None,
        description="会话 ID，用于关联历史消息",
        examples=["conv_001"],
    )

    knowledge_base_id: str | None = Field(
        default=None,
        description="知识库 ID，用于 RAG 检索隔离",
        examples=["kb_001"],
    )

    client_ip: str | None = Field(
        default=None,
        description="客户端 IP，用于审计、风控和限流",
        examples=["127.0.0.1"],
    )

    user_agent: str | None = Field(
        default=None,
        description="客户端 User-Agent，用于审计和问题排查",
    )

    auth_type: str = Field(
        default="api_key",
        description="认证方式，早期可以是 api_key，后续可扩展为 jwt/oauth2/sso",
        examples=["api_key"],
    )

    roles: list[str] = Field(
        default_factory=list,
        description="用户角色，后续用于 RBAC 权限控制",
        examples=[["user"]],
    )

    permissions: list[str] = Field(
        default_factory=list,
        description="用户权限点，后续用于工具调用、知识库访问控制",
        examples=[["chat:write", "knowledge:read"]],
    )

    def log_extra(self) -> dict:
        """
        返回适合写入日志的上下文字段。

        注意：
        不在这里返回敏感信息，例如 token、api key、完整 prompt 等。
        """

        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "conversation_id": self.conversation_id,
            "knowledge_base_id": self.knowledge_base_id,
            "client_ip": self.client_ip,
            "auth_type": self.auth_type,
        }

    def rag_filter(self) -> dict:
        """
        返回 RAG 检索时使用的 metadata filter。

        Chroma 多条件过滤需要使用 $and，
        不能直接写成 {"tenant_id": "...", "knowledge_base_id": "..."}。
        """

        filters = [
            {
                "tenant_id": self.tenant_id,
            },
            {
                "status": "active",
            },
        ]

        if self.knowledge_base_id:
            filters.append(
                {
                    "knowledge_base_id": self.knowledge_base_id,
                }
            )

        if len(filters) == 1:
            return filters[0]

        return {
            "$and": filters,
        }
    
    def with_conversation_id(self, conversation_id: str | None) -> "RequestContext":
        """
        返回带 conversation_id 的新上下文。

        如果调用方传了 conversation_id，则使用调用方的。
        如果没有传，则生成一个新的临时会话 ID。

        注意：
        当前阶段只是生成 ID。
        后续接数据库后，这里可以改为由 ConversationService 创建会话。
        """

        return self.model_copy(
            update={
                "conversation_id": conversation_id or f"conv_{uuid4().hex}",
            }
        )
