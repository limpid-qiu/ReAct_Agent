from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """
    单条历史消息。

    role:
    - user：用户消息
    - assistant：AI 回复

    content:
    - 消息正文
    """

    role: str = Field(
        ...,
        description="消息角色，只建议使用 user 或 assistant",
        examples=["user"],
    )
    content: str = Field(
        ...,
        description="消息内容",
        examples=["扫地机器人怎么保养？"],
    )


class ChatRequest(BaseModel):
    """
    聊天请求参数。

    query:
    - 当前用户输入的问题。

    conversation_id:
    - 会话 ID。
    - 早期可以不传，由前端或后端临时生成。
    - 后续接数据库后，用它来关联历史消息。

    history:
    - 当前会话历史消息。
    - 早期可以由前端传入。
    - 企业级版本建议改成从数据库读取。
    """

    query: str = Field(
        ...,
        min_length=1,
        description="用户当前输入的问题",
        examples=["推荐一款适合小户型的扫地机器人"],
    )

    conversation_id: str | None = Field(
        default=None,
        description="会话 ID，用于关联上下文",
        examples=["conv_001"],
    )

    history: list[ChatMessage] = Field(
        default_factory=list,
        description="历史对话消息",
    )


class ChatResponse(BaseModel):
    """
    普通聊天响应。

    answer:
    - Agent 最终生成的完整回答。

    request_id:
    - 当前请求 ID，用于日志追踪。

    conversation_id:
    - 当前会话 ID。
    - 如果后续由后端自动创建会话，需要通过这个字段返回给前端。
    """

    answer: str = Field(
        ...,
        description="Agent 返回的回答内容",
    )

    request_id: str = Field(
        ...,
        description="请求 ID，用于日志追踪和问题排查",
        examples=["req_01HYX9QK7M8N3P2A1B4C5D6E7F"],
    )

    conversation_id: str | None = Field(
        default=None,
        description="会话 ID，用于前端继续关联上下文",
        examples=["conv_001"],
    )


class ChatStreamChunk(BaseModel):
    """
    流式响应片段。

    注意：
    当前如果使用 StreamingResponse 返回 text/plain，
    这个模型暂时不会直接用到。

    后续如果升级成 SSE 或 WebSocket，可以用它规范每个 chunk 的格式。
    """

    content: str = Field(
        ...,
        description="当前流式输出片段",
    )

    done: bool = Field(
        default=False,
        description="是否输出结束",
    )