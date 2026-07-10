from contextlib import contextmanager
from threading import BoundedSemaphore
from collections.abc import Generator

from fastapi import HTTPException, status
from app.core.config import get_settings


class ModelConcurrencyLimiter:
    """
    模型并发限制器。

    当前阶段使用进程内 BoundedSemaphore。
    适合本地开发和单进程部署验证。

    生产环境：
    - 多进程 / 多机器时需要 Redis、队列或 API Gateway 配合。
    """

    def __init__(self, max_concurrent: int) -> None:
        self._semaphore = BoundedSemaphore(value=max_concurrent)

    @contextmanager
    def acquire(self) -> Generator[None, None, None]:
        acquired = self._semaphore.acquire(blocking=False)

        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="当前模型调用繁忙，请稍后再试",
            )

        try:
            yield
        finally:
            self._semaphore.release()


settings = get_settings()

model_concurrency_limiter = ModelConcurrencyLimiter(
    max_concurrent=settings.model_max_concurrent,
)