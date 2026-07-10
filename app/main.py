from pathlib import Path
from time import perf_counter

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.core.metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION_SECONDS

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import chat, conversations, health, knowledge, monitoring, tools
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

def create_app() -> FastAPI:
    """
    创建 FastAPI 应用实例。

    这个函数负责：
    1. 读取应用配置。
    2. 创建 FastAPI app。
    3. 配置跨域 CORS。
    4. 注册各个 API 路由。
    """

    settings = get_settings()
    setup_logging(debug=settings.debug)

    app = FastAPI(
        title=settings.app_name,
        description="基于 ReAct Agent 和 RAG 的智能问答服务",
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # 配置 CORS 跨域。
    #
    # 开发阶段 settings.cors_origins 通常是 ["*"]。
    # 生产环境建议通过 .env 改成明确域名。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册全局异常处理器。
    register_exception_handlers(app)

    # 根路径接口。
    # 访问 http://127.0.0.1:8000/ 时返回服务基本信息。
    @app.get("/")
    def root() -> dict:
        return {
            "message": f"{settings.app_name} is running",
            "env": settings.app_env,
            "docs": "/docs",
            "health": "/api/health",
        }

    # 注册健康检查路由。
    
    # 最终路径：
    # GET /api/health
    app.include_router(
        health.router,
        prefix="/api",
        tags=["Health"],
    )

    # 注册聊天路由。
    #
    # 最终路径：
    # POST /api/chat/
    # POST /api/chat/stream
    app.include_router(
        chat.router,
        prefix="/api/chat",
        tags=["Chat"],
    )

    # 用来查看某个会话及消息
    app.include_router(
        conversations.router,
        prefix="/api/conversations",
        tags=["Conversations"],
    )

    # 注册知识库路由。
    #
    # 最终路径：
    # GET  /api/knowledge/pending-files
    # POST /api/knowledge/rebuild
    app.include_router(
        knowledge.router,
        prefix="/api/knowledge",
        tags=["Knowledge"],
    )

    app.include_router(
        monitoring.router,
        prefix="/api/monitoring",
        tags=["Monitoring"],
    )

    app.include_router(
        tools.router,
        prefix="/api/tools",
        tags=["Tools"],
    )

    if Path("frontend").exists():
        app.mount(
            "/ui",
            StaticFiles(directory="frontend", html=True),
            name="ui",
        )

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        started_at = perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            path = request.url.path
            method = request.method

            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                path=path,
                status=str(status_code),
            ).inc()

            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                path=path,
            ).observe(perf_counter() - started_at)

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


# Uvicorn 启动时会寻找这个 app 对象。
#
# 常用启动命令：
# uvicorn app.main:app --reload
app = create_app()


# 允许直接通过 Python 运行：
# python -m app.main
if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


