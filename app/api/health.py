from fastapi import APIRouter


# 创建一个路由对象。
# main.py 里会这样注册：
# app.include_router(health.router, prefix="/api", tags=["Health"])
#
# 所以这里的 "/" 最终路径是：
# GET /api/health
router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    """
    健康检查接口。

    作用：
    - 本地开发时确认服务是否启动成功。
    - Docker / Kubernetes 可以用它判断容器是否存活。
    - 监控系统可以定期请求这个接口判断服务状态。

    返回：
    - status: ok 表示 API 服务本身正常运行。
    """

    return {
        "status": "ok",
        "service": "react-agent-api",
    }