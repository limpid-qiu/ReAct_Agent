from collections import defaultdict, deque
from time import monotonic

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.schemas.context import RequestContext


class InMemoryRateLimiter:
    """
    内存版滑动窗口限流器。

    当前阶段用于本地开发和验证限流逻辑。

    注意：
    - 只对当前 Python 进程有效。
    - 多进程、多机器部署时不共享状态。
    - 生产环境应替换为 Redis token bucket / sliding window。
    """

    def __init__(self) -> None:
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def check(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        """
        检查某个 key 在窗口期内是否超过限制。

        key:
        - 可以是 user:user_001
        - 可以是 tenant:default

        limit:
        - 窗口内最多允许多少次请求

        window_seconds:
        - 窗口大小，单位秒
        """

        now = monotonic()
        window_start = now - window_seconds

        records = self._requests[key]

        while records and records[0] < window_start:
            records.popleft()

        if len(records) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
            )

        records.append(now)


rate_limiter = InMemoryRateLimiter()


def check_chat_rate_limit(context: RequestContext) -> None:
    settings = get_settings()

    rate_limiter.check(
        key=f"user:{context.user_id}",
        limit=settings.chat_user_rate_limit,
        window_seconds=settings.chat_rate_limit_window_seconds,
    )

    rate_limiter.check(
        key=f"tenant:{context.tenant_id}",
        limit=settings.chat_tenant_rate_limit,
        window_seconds=settings.chat_rate_limit_window_seconds,
    )