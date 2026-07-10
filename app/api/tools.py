from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from agent.tools.registry import get_enabled_tool_definitions, get_tool_definition
from app.core.request_context import (
    reset_current_request_context,
    set_current_request_context,
)
from app.core.security import get_request_context, require_permission
from app.schemas.context import RequestContext


router = APIRouter()


class ToolInfo(BaseModel):
    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具说明")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="入参结构")
    timeout_seconds: float = Field(..., description="建议超时时间")
    side_effect: bool = Field(default=False, description="是否有副作用")


class ToolListResponse(BaseModel):
    tools: list[ToolInfo] = Field(default_factory=list, description="当前身份可用工具")


class ToolInvokeRequest(BaseModel):
    args: dict[str, Any] = Field(default_factory=dict, description="工具调用参数")


class ToolInvokeResponse(BaseModel):
    tool_name: str = Field(..., description="工具名称")
    request_id: str = Field(..., description="请求 ID")
    result: Any = Field(default=None, description="工具调用结果")


@router.get("", response_model=ToolListResponse)
def list_tools(
    context: RequestContext = Depends(get_request_context),
) -> ToolListResponse:
    tools = []

    for definition in get_enabled_tool_definitions():
        if definition.permission and definition.permission not in context.permissions:
            continue

        tools.append(
            ToolInfo(
                name=definition.tool_name,
                description=definition.description,
                input_schema=definition.input_schema,
                timeout_seconds=definition.timeout_seconds,
                side_effect=definition.side_effect,
            )
        )

    return ToolListResponse(tools=tools)


@router.post("/{tool_name}/invoke", response_model=ToolInvokeResponse)
def invoke_tool(
    tool_name: str,
    request: ToolInvokeRequest,
    context: RequestContext = Depends(get_request_context),
) -> ToolInvokeResponse:
    try:
        definition = get_tool_definition(tool_name)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"工具不存在：{tool_name}",
        ) from exc

    if not definition.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"工具未启用：{tool_name}",
        )

    if definition.permission:
        require_permission(context, definition.permission)

    token = set_current_request_context(context)

    try:
        result = definition.tool.invoke(request.args)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"工具调用失败：{definition.tool_name}",
        ) from exc
    finally:
        reset_current_request_context(token)

    return ToolInvokeResponse(
        tool_name=definition.tool_name,
        request_id=context.request_id,
        result=result,
    )
