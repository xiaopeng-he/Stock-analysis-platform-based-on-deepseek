"""自选股 ORM 模型。"""

from sqlalchemy import Column, Integer, String, Float, DateTime, func

from app.models.database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, unique=True, comment="股票代码")
    stock_name = Column(String(20), nullable=False, comment="股票名称")
    exchange = Column(String(4), nullable=False, default="SZ", comment="交易所 SZ/SH/BJ")
    added_at = Column(DateTime, server_default=func.now(), comment="添加时间")
    is_active = Column(Integer, default=1, comment="是否启用")
    entry_price = Column(Float, default=0.0, comment="买入成本价（0=仅关注）")
    shares = Column(Integer, default=0, comment="持仓数量（0=仅关注）")
    notes = Column(String(200), default="", comment="个人备注")
