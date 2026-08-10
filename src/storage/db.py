"""
数据库初始化与会话管理 (DESIGN.md §7.1)

原型阶段使用 SQLite WAL 模式，SQLAlchemy ORM。
大字段（转写文本、文档内容、纪要结果）采用文件存储 + 数据库记录路径。
"""

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import get_config

config = get_config()

# 解析数据库路径，确保目录存在
db_url = config.DATABASE_URL
if db_url.startswith("sqlite:///"):
    db_path = db_url.replace("sqlite:///", "")
    # 将相对路径转为绝对路径
    db_path = config.resolve_path(db_path)
    # 确保目录存在
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_url = f"sqlite:///{db_path}"

# 创建引擎
# SQLite: check_same_thread=False 以支持 FastAPI 异步
connect_args = {}
if "sqlite" in db_url:
    connect_args["check_same_thread"] = False

engine = create_engine(
    db_url,
    echo=config.DEBUG,
    connect_args=connect_args,
    pool_pre_ping=True,
)

# 会话工厂
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# SQLite WAL 模式启用
if config.SQLITE_WAL_MODE and "sqlite" in db_url:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话（FastAPI 依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """初始化数据库：创建所有表"""
    import src.storage.models  # noqa: F401 — 确保模型注册
    Base.metadata.create_all(bind=engine)