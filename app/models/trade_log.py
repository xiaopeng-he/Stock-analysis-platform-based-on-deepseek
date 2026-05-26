"""交易日志 ORM 模型——记录买入卖出、复盘。"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, func
from app.models.database import Base


class TradeLog(Base):
    __tablename__ = "trade_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False)
    stock_name = Column(String(20))
    action = Column(String(10), nullable=False, comment="买入/卖出")
    price = Column(Float, nullable=False)
    shares = Column(Integer, nullable=False)
    amount = Column(Float, comment="成交金额")
    reason = Column(Text, comment="交易理由")
    emotion = Column(String(20), comment="交易时情绪: 理性/冲动/贪婪/恐惧/跟风")
    mistake_type = Column(String(30), comment="错误类型: 追高/杀跌/仓位过重/频繁交易/无/")
    lesson = Column(Text, comment="经验教训")
    created_at = Column(DateTime, server_default=func.now())

    # 复盘字段
    result_pnl = Column(Float, default=0.0, comment="盈亏(卖出后回填)")
    reviewed = Column(Integer, default=0, comment="是否已复盘")
    review_notes = Column(Text, comment="复盘笔记")
