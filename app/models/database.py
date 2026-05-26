"""数据库配置——SQLAlchemy engine 和 session，以及初始化入口。"""

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import config

# SQLAlchemy engine（使用 echo=False 关闭调试日志）
engine = create_engine(config.DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI 依赖注入用——获取数据库 session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库——创建所有表、自动迁移新列。"""
    # 确保所有模型已导入
    from app.models.watchlist import WatchlistItem  # noqa
    from app.models.analysis_log import AnalysisLog  # noqa
    from app.models.trade_log import TradeLog  # noqa

    data_dir = Path(__file__).parent.parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    # 自动迁移：为已有表添加新列
    import sqlite3
    db_path = data_dir / "astock.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("PRAGMA table_info(watchlist)")
        columns = {row[1] for row in cur.fetchall()}
        if "entry_price" not in columns:
            conn.execute("ALTER TABLE watchlist ADD COLUMN entry_price REAL DEFAULT 0.0")
        if "shares" not in columns:
            conn.execute("ALTER TABLE watchlist ADD COLUMN shares INTEGER DEFAULT 0")
        if "notes" not in columns:
            conn.execute("ALTER TABLE watchlist ADD COLUMN notes VARCHAR(200) DEFAULT ''")
        conn.commit()
        conn.close()
