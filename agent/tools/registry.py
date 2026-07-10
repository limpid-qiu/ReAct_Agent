from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool

from agent.tools.agent_tools import (
    fetch_external_data,
    fill_context_for_report,
    get_current_month,
    get_user_id,
    get_weather,
    rag_summarize,
)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0.0


@dataclass(frozen=True)
class ToolDefinition:
    tool_name: str
    tool: BaseTool
    description: str
    input_schema: dict[str, Any]
    timeout_seconds: float
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    permission: str | None = None
    audit_enabled: bool = True
    enabled: bool = True
    sensitive_fields: tuple[str, ...] = ()
    fallback_message: str | None = None
    side_effect: bool = False
    idempotency_required: bool = False


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "rag_summarize": ToolDefinition(
        tool_name="rag_summarize",
        tool=rag_summarize,
        description="基于当前租户和知识库上下文进行 RAG 问答。",
        input_schema={
            "query": "str",
        },
        timeout_seconds=30,
        permission="tool:rag_summarize",
        fallback_message="知识库暂时不可用，请基于通用扫地/扫拖机器人知识谨慎回答，并提示用户稍后重试。",
        side_effect=False,
        idempotency_required=False,
    ),
    "get_weather": ToolDefinition(
        tool_name="get_weather",
        tool=get_weather,
        description="通过高德地图 API 获取指定城市天气。",
        input_schema={
            "city": "str",
        },
        timeout_seconds=20,
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0.5),
        permission="tool:get_weather",
        fallback_message="暂时无法获取实时天气，请基于常规天气、湿度和地面环境给出扫地机器人使用建议。",
        side_effect=False,
        idempotency_required=False,
    ),
    "get_user_id": ToolDefinition(
        tool_name="get_user_id",
        tool=get_user_id,
        description="获取当前演示环境中的用户 ID。",
        input_schema={},
        timeout_seconds=5,
        permission="tool:get_user_id",
    ),
    "get_current_month": ToolDefinition(
        tool_name="get_current_month",
        tool=get_current_month,
        description="获取当前月份，格式为 YYYY-MM。",
        input_schema={},
        timeout_seconds=5,
        permission="tool:get_current_month",
        audit_enabled=False,
    ),
    "fetch_external_data": ToolDefinition(
        tool_name="fetch_external_data",
        tool=fetch_external_data,
        description="读取指定用户和月份的外部使用记录。",
        input_schema={
            "user_id": "str",
            "month": "str",
        },
        timeout_seconds=10,
        permission="tool:fetch_external_data",
        sensitive_fields=("user_id",),
        fallback_message="暂时无法获取用户使用记录，请提示用户稍后重试，不要编造用户报告数据。",
        side_effect=False,
        idempotency_required=False,
    ),
    "fill_context_for_report": ToolDefinition(
        tool_name="fill_context_for_report",
        tool=fill_context_for_report,
        description="标记当前 Agent run 进入报告生成场景。",
        input_schema={},
        timeout_seconds=5,
        permission="tool:fill_context_for_report",
        side_effect=False,
        idempotency_required=False,
    ),
}


def get_tool_definition(tool_name: str) -> ToolDefinition:
    return TOOL_REGISTRY[tool_name]


def get_enabled_tool_definitions() -> list[ToolDefinition]:
    return [definition for definition in TOOL_REGISTRY.values() if definition.enabled]


def get_enabled_tools() -> list[BaseTool]:
    return [definition.tool for definition in get_enabled_tool_definitions()]
