from contextvars import ContextVar, Token

from app.schemas.context import RequestContext


_current_request_context: ContextVar[RequestContext | None] = ContextVar(
    "current_request_context",
    default=None,
)


def set_current_request_context(context: RequestContext) -> Token:
    return _current_request_context.set(context)


def reset_current_request_context(token: Token) -> None:
    _current_request_context.reset(token)


def get_current_request_context() -> RequestContext:
    context = _current_request_context.get()

    if context is None:
        raise RuntimeError("当前请求上下文不存在，无法执行需要租户隔离的操作")

    return context