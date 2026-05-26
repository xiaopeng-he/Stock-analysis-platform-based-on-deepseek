"""股票数据 API——K线数据等数据接口。"""

from fastapi import APIRouter, Query

from app.services.data_service import data_service

router = APIRouter()


@router.get("/stock/{stock_code}/kline")
async def get_kline(stock_code: str, period: str = Query(default="5", pattern="^(1|5|15|30|60|daily)$")):
    """获取 K 线数据——支持1/5/15/30/60分钟和日K。"""
    if period == "daily":
        klines = data_service.get_daily_kline(stock_code)
    else:
        klines = data_service.get_minute_kline(stock_code, period=period)
    return {"code": stock_code, "period": period, "klines": klines}
