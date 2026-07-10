from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    应用配置。

    BaseSettings 的作用：
    - 可以从环境变量读取配置。
    - 可以从 .env 文件读取配置。
    - 可以给配置设置默认值。
    - 可以对配置类型做校验。

    这样后续就不用在项目里到处写 os.getenv()。
    """

    # 当前运行环境。
    # 常见值：
    # - dev：本地开发
    # - test：测试环境
    # - prod：生产环境
    app_env: str = Field(
        default="dev",
        description="应用运行环境",
    )

    # 应用名称。
    app_name: str = Field(
        default="ReAct Agent API",
        description="应用名称",
    )

    # API 版本号。
    app_version: str = Field(
        default="0.1.0",
        description="应用版本",
    )

    # 是否开启 debug。
    debug: bool = Field(
        default=True,
        description="是否开启调试模式",
    )

    # 服务监听地址。
    host: str = Field(
        default="127.0.0.1",
        description="服务监听地址",
    )

    # 服务监听端口。
    port: int = Field(
        default=8000,
        description="服务监听端口",
    )

    # CORS 允许的来源。
    #
    # 开发阶段可以用 ["*"]。
    # 生产环境建议配置成明确域名。
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"],
        description="允许跨域访问的来源列表",
    )

    api_key: str | None = Field(
    default=None,
    description="可选 API Key；为空时不启用 API Key 鉴权",
    )
    security_strict_mode: bool = Field(
        default=False,
        description="是否启用严格安全模式",
    )

    allow_demo_headers: bool = Field(
        default=True,
        description="是否允许通过 X-User-ID / X-Tenant-ID 演示身份",
    )

    allow_empty_tool_permissions: bool = Field(
        default=True,
        description="是否允许空工具权限兼容本地 demo",
    )

    # 后续可继续增加：
    # database_url: str
    # redis_url: str
    # jwt_secret_key: str
    # access_token_expire_minutes: int
    # vector_store_url: str

    database_url: str = Field(
    default="sqlite:///./data/app.db",
    description="数据库连接地址",
    )

    model_max_concurrent: int = Field(
    default=3,
    description="模型最大并发调用数",
    )

    chat_user_rate_limit: int = Field(
    default=20,
    description="单用户 Chat 接口限流次数",
    )

    chat_tenant_rate_limit: int = Field(
        default=100,
        description="单租户 Chat 接口限流次数",
    )


    knowledge_upload_dir: str = Field(
        default="data/uploads",
        description="知识库上传文件存储目录",
    )

    max_upload_file_size_mb: int = Field(
        default=20,
        description="知识库单个上传文件最大大小，单位 MB",
    )

    chat_rate_limit_window_seconds: int = Field(
        default=60,
        description="Chat 接口限流窗口秒数",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_keys_config_path: str = Field(
    default="config/api_keys.yml",
    description="API Key 绑定配置文件路径",
    )


@lru_cache
def get_settings() -> Settings:
    """
    获取全局配置对象。

    使用 lru_cache 的原因：
    - Settings 只需要初始化一次。
    - 避免每次调用都重新读取 .env。
    - FastAPI 依赖注入时也常用这种写法。
    """

    return Settings()

