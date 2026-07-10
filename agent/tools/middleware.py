import re
from copy import deepcopy
from time import perf_counter,sleep
from typing import Callable
from langchain.agents import AgentState
from langchain.agents.middleware import (
    ModelRequest, 
    ModelResponse, 
    before_model, 
    after_model, 
    wrap_tool_call, 
    dynamic_prompt)
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from agent.tools.registry import ToolDefinition, get_tool_definition
from utils.prompts_loader import report_prompt, system_prompt
from app.core.logging import get_logger
from app.core.request_context import get_current_request_context
from app.db.session import SessionLocal
from app.services.tool_audit_service import ToolAuditService
from app.core.metrics import (
    MODEL_CALLS_TOTAL,
    MODEL_CALL_DURATION_SECONDS,
    TOOL_CALLS_TOTAL,
    TOOL_CALL_DURATION_SECONDS,
)

from app.core.config import get_settings

logger = get_logger(__name__)
tool_audit_service = ToolAuditService()

def get_context_log_extra() -> dict:
    try:
        return get_current_request_context().log_extra()
    except RuntimeError:
        return {}
    
def record_tool_audit(
    tool_name: str,
    input_summary: dict | None,
    output_summary: str | None,
    status: str,
    latency_ms: int | None = None,
    error_message: str | None = None,
) -> None:
    try:
        context = get_current_request_context()
    except RuntimeError:
        context = None

    db = SessionLocal()

    try:
        tool_audit_service.record_tool_call(
            db=db,
            context=context,
            tool_name=tool_name,
            input_summary=input_summary,
            output_summary=output_summary,
            status=status,
            latency_ms=latency_ms,
            error_message=error_message,
        )
    except Exception as exc:
        logger.warning(
            "tool_audit_record_failed",
            extra={
                "tool_name": tool_name,
                "status": status,
                "error_message": str(exc),
            },
        )
    finally:
        db.close()
    
def mask_sensitive_args(args: dict, sensitive_fields: tuple[str, ...]) -> dict:
    masked_args = deepcopy(args)

    for field in sensitive_fields:
        if field in masked_args:
            masked_args[field] = "***"

    return masked_args

def check_tool_permission(definition: ToolDefinition) -> None:
    context = get_current_request_context()
    tool_name = definition.tool_name

    if not definition.enabled:
        raise PermissionError(f"工具已禁用：{tool_name}")

    if not definition.permission:
        return

    # 兼容当前 demo：如果 permissions 为空，暂时放行。
    # 后续进入严格 RBAC 后，可以改成空权限也拒绝。
    if not context.permissions:
        settings = get_settings()

        if settings.allow_empty_tool_permissions:
            return

        raise PermissionError(
            f"当前用户无权调用工具：{tool_name}，权限列表为空"
        )

    if definition.permission not in context.permissions:
        raise PermissionError(
            f"当前用户无权调用工具：{tool_name}，需要权限：{definition.permission}"
        )
    
def is_valid_month(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value))

def validate_tool_args(definition: ToolDefinition, args: dict) -> None:
    tool_name = definition.tool_name
    input_schema = definition.input_schema

    for field_name, field_type in input_schema.items():
        if field_name not in args:
            raise ValueError(f"工具 {tool_name} 缺少参数：{field_name}")

        value = args[field_name]

        if field_type == "str" and not isinstance(value, str):
            raise ValueError(f"工具 {tool_name} 参数 {field_name} 必须是字符串")

        if isinstance(value, str) and not value.strip():
            raise ValueError(f"工具 {tool_name} 参数 {field_name} 不能为空")

    if tool_name == "fetch_external_data":
        month = args.get("month", "")
        if not is_valid_month(month):
            raise ValueError(f"工具 {tool_name} 参数 month 格式必须是 YYYY-MM")

    if tool_name == "get_weather":
        city = args.get("city", "")
        if len(city) > 50:
            raise ValueError("城市名称过长")

    if tool_name == "rag_summarize":
        query = args.get("query", "")
        if len(query) > 500:
            raise ValueError("RAG 检索 query 过长")
        
def check_tool_workflow(definition: ToolDefinition, request: ToolCallRequest) -> None:
    tool_name = definition.tool_name

    if tool_name != "fetch_external_data":
        return

    is_report = request.runtime.context.get("report", False)

    if not is_report:
        raise PermissionError(
            "调用 fetch_external_data 前必须先调用 fill_context_for_report"
        )

def execute_tool_with_retry(
    definition: ToolDefinition,
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    retry_policy = definition.retry_policy
    max_attempts = max(1, retry_policy.max_attempts)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return handler(request)

        except Exception as e:
            last_error = e

            if attempt >= max_attempts:
                break

            logger.warning(
                "tool_call_retrying",
                extra={
                    **get_context_log_extra(),
                    "tool_name": definition.tool_name,
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "error_message": str(e),
                },
            )

            if retry_policy.backoff_seconds > 0:
                sleep(retry_policy.backoff_seconds)

    if last_error:
        if definition.fallback_message:
            logger.warning(
                "tool_call_fallback",
                extra={
                    **get_context_log_extra(),
                    "tool_name": definition.tool_name,
                    "error_message": str(last_error),
                    "fallback_message": definition.fallback_message,
                },
            )
            return ToolMessage(
                content=definition.fallback_message,
                tool_call_id=request.tool_call["id"],
            )
        raise last_error

    raise RuntimeError(f"工具 {definition.tool_name} 执行失败")

def check_idempotency(definition: ToolDefinition, args: dict) -> None:
    if not definition.idempotency_required:
        return

    idempotency_key = args.get("idempotency_key")

    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError(
            f"工具 {definition.tool_name} 是副作用工具，必须提供 idempotency_key"
        )

@wrap_tool_call
def monitor_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    log_extra = get_context_log_extra()
    tool_name = request.tool_call["name"]
    tool_args = request.tool_call.get("args", {})

    try:
        definition = get_tool_definition(tool_name)
    except KeyError:
        raise PermissionError(f"工具未注册：{tool_name}")

    if not isinstance(tool_args, dict):
        raise ValueError(f"工具 {tool_name} 参数必须是对象")

    masked_args = mask_sensitive_args(
        args=tool_args,
        sensitive_fields=definition.sensitive_fields,
    )

    if definition.audit_enabled:
        logger.info(
            f"[tool monitor]执行工具：{tool_name}",
            extra=log_extra,
        )
        logger.info(
            f"[tool monitor]传入参数：{masked_args}",
            extra=log_extra,
        )

    started_at = perf_counter()

    try:
        check_tool_permission(definition)
        validate_tool_args(definition, tool_args)
        check_tool_workflow(definition, request)
        check_idempotency(definition, tool_args)

        result = execute_tool_with_retry(
            definition=definition,
            request=request,
            handler=handler,
        )

        latency_ms = int((perf_counter() - started_at) * 1000)

        logger.info(
            "tool_call_finished",
            extra={
                **log_extra,
                "tool_name": tool_name,
                "input_summary": masked_args,
                "status": "success",
                "latency_ms": latency_ms,
            },
        )

        record_tool_audit(
            tool_name=tool_name,
            input_summary=masked_args,
            output_summary=str(result)[:1000],
            status="success",
            latency_ms=latency_ms,
        )
        TOOL_CALLS_TOTAL.labels(
            tool_name=tool_name,
            status="success",
        ).inc()

        TOOL_CALL_DURATION_SECONDS.labels(
            tool_name=tool_name,
        ).observe(latency_ms / 1000)

        if tool_name == "fill_context_for_report":
            request.runtime.context["report"] = True

        return result

    except Exception as e:
        latency_ms = int((perf_counter() - started_at) * 1000)

        logger.error(
            "tool_call_failed",
            extra={
                **log_extra,
                "tool_name": tool_name,
                "input_summary": masked_args,
                "status": "failed",
                "latency_ms": latency_ms,
                "error_message": str(e),
            },
        )

        record_tool_audit(
            tool_name=tool_name,
            input_summary=masked_args,
            output_summary=None,
            status="failed",
            latency_ms=latency_ms,
            error_message=str(e),
        )
        TOOL_CALLS_TOTAL.labels(
            tool_name=tool_name,
            status="failed",
        ).inc()

        TOOL_CALL_DURATION_SECONDS.labels(
            tool_name=tool_name,
        ).observe(latency_ms / 1000)
        raise
    
@before_model
def log_before_model(
        state: AgentState,          # 整个Agent智能体中的状态记录
        runtime: Runtime,           # 记录了整个执行过程中的上下文信息
):         # 在模型执行前输出日志
    runtime.context["model_started_at"] = perf_counter()
    log_extra = get_context_log_extra()

    logger.info(
        f"[log_before_model]即将调用模型，带有{len(state['messages'])}条消息。",
        extra=log_extra,
    )

    latest_content = state["messages"][-1].content.strip()
    if len(latest_content) > 500:
        latest_content = latest_content[:500] + "...[truncated]"

    logger.debug(
        f"[log_before_model]{type(state['messages'][-1]).__name__} | {latest_content}",
        extra=log_extra,
    )

    return None

@after_model
def log_after_model(
    state: AgentState,
    runtime: Runtime,
):
    log_extra = get_context_log_extra()

    started_at = runtime.context.pop("model_started_at", None)
    latency_ms = None

    if started_at is not None:
        latency_ms = int((perf_counter() - started_at) * 1000)

    MODEL_CALLS_TOTAL.labels(status="success").inc()

    if latency_ms is not None:
        MODEL_CALL_DURATION_SECONDS.observe(latency_ms / 1000)

    messages = state["messages"] if "messages" in state else []
    latest_message = messages[-1] if messages else None
    output = getattr(latest_message, "content", "") if latest_message else ""

    logger.info(
        "model_call_finished",
        extra={
            **log_extra,
            "latency_ms": latency_ms,
            "message_count": len(messages),
            "output_length": len(output or ""),
        },
    )

    return None


@dynamic_prompt                 # 每一次在生成提示词之前，调用此函数
def report_prompt_switch(request: ModelRequest):     # 动态切换提示词
    is_report = request.runtime.context.get("report", False)
    if is_report:               # 是报告生成场景，返回报告生成提示词内容
        return report_prompt

    return system_prompt




