"""AI 分析历史 ORM 模型。"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, func

from app.models.database import Base


class AnalysisLog(Base):
    __tablename__ = "analysis_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, comment="股票代码")
    stock_name = Column(String(20), nullable=False, comment="股票名称")
    analysis_type = Column(String(20), nullable=False, default="realtime", comment="分析类型")
    price = Column(Float, comment="分析时价格")
    change_pct = Column(Float, comment="分析时涨跌幅")
    ai_summary = Column(Text, comment="AI 分析摘要")
    ai_sentiment = Column(String(20), comment="情绪判断")
    ai_confidence = Column(Float, comment="置信度 0-1")
    raw_response = Column(Text, comment="DeepSeek 原始响应 JSON")
    token_usage = Column(Integer, comment="消耗 Token 数")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
