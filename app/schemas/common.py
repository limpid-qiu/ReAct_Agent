from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    通用错误响应结构。

    当前阶段主要用于文档说明。
    后续可以配合全局异常处理器，让所有错误都返回统一格式。

    示例：
    {
        "code": "AGENT_CALL_FAILED",
        "message": "Agent 调用失败",
        "detail": "具体错误信息"
    }
    """

    code: str = Field(
        ...,
        description="业务错误码",
        examples=["AGENT_CALL_FAILED"],
    )

    message: str = Field(
        ...,
        description="用户可读的错误说明",
        examples=["Agent 调用失败"],
    )

    detail: str | None = Field(
        default=None,
        description="详细错误信息，生产环境可选择不返回",
    )


class SuccessResponse(BaseModel):
    """
    通用成功响应结构。

    适合没有复杂返回数据的接口，例如删除成功、任务提交成功。
    """

    success: bool = Field(
        default=True,
        description="操作是否成功",
    )

    message: str = Field(
        default="ok",
        description="结果说明",
    )