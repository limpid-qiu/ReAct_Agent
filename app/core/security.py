from app.core.api_key_store import get_api_key_identity
from uuid import uuid4

from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings
from app.schemas.context import RequestContext

DEFAULT_DEMO_PERMISSIONS = [
    "chat:write",
    "conversation:read",
    "knowledge:read",
    "knowledge:write",
    "knowledge:delete",
    "tool:rag_summarize",
    "tool:get_weather",
    "tool:get_user_id",
    "tool:get_current_month",
    "tool:fetch_external_data",
    "tool:fill_context_for_report",
]


def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict | None:
    """
    校验 API Key。

    优先使用 config/api_keys.yml 中的 API Key 绑定身份。
    如果没有配置命中，则兼容旧的 settings.api_key。
    """

    identity = get_api_key_identity(x_api_key)

    if identity:
        return identity

    settings = get_settings()

    if not settings.api_key:
        return None

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 X-API-Key 请求头",
        )

    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无效的 API Key",
        )

    return None


def get_request_context(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    x_knowledge_base_id: str | None = Header(
        default=None,
        alias="X-Knowledge-Base-ID",
    ),
    user_agent: str | None = Header(default=None, alias="User-Agent"),
) -> RequestContext:
    """
    解析单次请求的业务上下文。

    当前阶段：
    - 继续支持 X-API-Key。
    - 通过 Header 传 user_id / tenant_id / knowledge_base_id。
    - request_id 如果前端没有传，则后端自动生成。

    后续企业级升级：
    - x_user_id / x_tenant_id 不应长期信任前端直接传入。
    - 应从 JWT、OAuth2、企业 SSO 或 API Key 绑定关系中解析出来。
    """

    settings = get_settings()
    identity = verify_api_key(x_api_key=x_api_key)

    if settings.security_strict_mode and not identity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="严格安全模式下必须提供有效 API Key",
        )

    if identity:
        x_user_id = identity.get("user_id")
        x_tenant_id = identity.get("tenant_id")
        roles = identity.get("roles", [])
        permissions = identity.get("permissions", [])
    else:
        if not settings.allow_demo_headers:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="当前环境不允许使用演示身份请求头",
            )

        roles = ["user"]
        permissions = DEFAULT_DEMO_PERMISSIONS

    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少 X-User-ID 请求头",
        )

    if not x_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少 X-Tenant-ID 请求头",
        )

    client_ip = request.client.host if request.client else None

    return RequestContext(
        request_id=x_request_id or f"req_{uuid4().hex}",
        user_id=x_user_id,
        tenant_id=x_tenant_id,
        knowledge_base_id=x_knowledge_base_id,
        client_ip=client_ip,
        user_agent=user_agent,
        auth_type="api_key",
        roles=roles,
        permissions=permissions,
    )

def require_permission(
    context: RequestContext,
    permission: str,
) -> None:
    if permission not in context.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"缺少权限：{permission}",
        )
