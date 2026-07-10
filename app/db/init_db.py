from app.db.models import Base
from app.db.session import engine


def init_db() -> None:
    """
    创建数据库表。

    当前阶段用于本地开发。
    后续生产环境建议改成 Alembic migration。
    """

    Base.metadata.create_all(bind=engine)