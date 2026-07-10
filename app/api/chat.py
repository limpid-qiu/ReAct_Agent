from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.core.security import get_request_context, require_permission
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.context import RequestContext
from app.services.agent_service import AgentService
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.rate_limit import check_chat_rate_limit
from app.core.logging import get_logger
from app.core.prompt_guard import inspect_prompt_text


# 创建聊天路由对象。
# main.py 中会这样注册：
# app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
#
# 因此：
# 这里的 POST "/"      -> 最终路径 POST /api/chat/
# 这里的 POST "/stream" -> 最终路径 POST /api/chat/stream
router = APIRouter()


# 创建 AgentService 实例。
#
# 当前阶段：
# - 直接在模块加载时初始化，简单直观。
#
# 后续企业级优化：
# - 可以改成 FastAPI 依赖注入。
# - 可以在应用启动时初始化。
# - 可以加入连接池、模型客户端复用、限流器等。
agent_service = AgentService()
logger = get_logger(__name__)


@router.post("/", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    context: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    普通聊天接口。

    第二阶段变化：
    - 从 Header 解析 RequestContext。
    - 不再只依赖 request.conversation_id。
    - 将 conversation_id 合并进 context 后传给 AgentService。
    """

    try:
        require_permission(context, "chat:write")
        guard_result = inspect_prompt_text(request.query)

        if guard_result.suspicious:
            logger.warning(
                "prompt_injection_suspected",
                extra={
                    **context.log_extra(),
                    "matched_patterns": ",".join(guard_result.matched_patterns),
                },
            )
        context = context.with_conversation_id(request.conversation_id)
        check_chat_rate_limit(context)

        result = agent_service.chat(
            db=db,
            query=request.query,
            history=request.history,
            context=context,
        )

        return ChatResponse(
            answer=result.answer,
            request_id=context.request_id,
            conversation_id=result.conversation_id,
        )

    except HTTPException:
        raise

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "chat request failed",
            extra=context.log_extra(),
        )
        raise HTTPException(
            status_code=500,
            detail="Agent 调用失败，请稍后重试",
        ) from exc


@router.post("/stream")
def chat_stream(
    request: ChatRequest,
    context: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    流式聊天接口。

    第二阶段变化：
    - 同样注入 RequestContext。
    - 流式调用也必须携带 user_id / tenant_id / request_id。
    """

    try:
        require_permission(context, "chat:write")
        guard_result = inspect_prompt_text(request.query)

        if guard_result.suspicious:
            logger.warning(
                "prompt_injection_suspected",
                extra={
                    **context.log_extra(),
                    "matched_patterns": ",".join(guard_result.matched_patterns),
                },
            )
        context = context.with_conversation_id(request.conversation_id)
        check_chat_rate_limit(context)

        return StreamingResponse(
            agent_service.chat_stream(
                db=db,
                query=request.query,
                history=request.history,
                context=context,
            ),
            media_type="text/plain; charset=utf-8",
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Agent 调用失败: {str(exc)}",
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc