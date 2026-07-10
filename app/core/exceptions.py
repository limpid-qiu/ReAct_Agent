from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class AppException(Exception):
    """
    应用业务异常。

    用于主动抛出可预期的业务错误。

    例如：
    - Agent 调用失败
    - 知识库加载失败
    - 参数不合法
    - 资源不存在

    好处：
    - 不用到处手写 HTTPException。
    - 可以统一错误码、错误信息和 HTTP 状态码。
    """

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        detail: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册全局异常处理器。

    在 main.py 中调用：
    register_exception_handlers(app)

    注册后：
    - AppException 会返回统一业务错误格式。
    - 未捕获异常会返回统一系统错误格式。
    """

    settings = get_settings()

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        """
        处理业务异常。

        这类异常通常是我们主动抛出的，
        例如知识库文件不存在、Agent 调用失败等。
        """

        logger.warning(
            "AppException: path=%s code=%s message=%s detail=%s",
            request.url.path,
            exc.code,
            exc.message,
            exc.detail,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail if settings.debug else None,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """
        处理未捕获异常。

        这类异常通常是代码 bug、第三方服务异常或未知错误。

        生产环境不建议把原始异常信息直接返回给前端，
        否则可能泄露敏感信息或内部实现细节。
        """

        logger.exception(
            "Unhandled exception: path=%s",
            request.url.path,
        )

        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_SERVER_ERROR",
                "message": "服务器内部错误",
                "detail": repr(exc) if settings.debug else None,
            },
        )