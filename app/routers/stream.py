"""SSE 实时推送端点——推送实时行情、AI 分析和新闻到前端。（v0.3 优化版）"""

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from app.services.data_service import data_service

logger = logging.getLogger(__name__)
router = APIRouter()

_last_analysis: dict[str, float] = {}


async def event_generator(stock_code: str):
    """SSE 事件生成器——行情每 3 秒、AI 每 90 秒、新闻每 5 分钟。"""
    last_news_time = 0.0
    last_price_time = 0.0
    tick = 0
    _last_price = None  # 去重：价格不变不推送

    while True:
        try:
            now = time.time()

            # 1) 实时行情（每 5 秒，价格变动才推送）
            if now - last_price_time >= 5:
                last_price_time = now
                quote = data_service.get_realtime_quote(stock_code)
                if quote:
                    cur_price = quote.get("price")
                    if cur_price != _last_price:
                        _last_price = cur_price
                        yield {"event": "price", "data": json.dumps(quote, ensure_ascii=False)}

            # 2) AI 分析（每 90 秒）
            last_ai = _last_analysis.get(stock_code, 0.0)
            if now - last_ai >= 90:
                _last_analysis[stock_code] = now
                try:
                    from app.services.ai_service import ai_service
                    analysis = await ai_service.analyze_stock(stock_code, quote if 'quote' in dir() else None)
                    if analysis:
                        yield {"event": "analysis", "data": json.dumps(analysis, ensure_ascii=False)}
                except Exception as e:
                    logger.warning(f"AI analysis failed for {stock_code}: {e}")

            # 3) 新闻（每 5 分钟）
            if now - last_news_time >= 300:
                last_news_time = now
                news = data_service.get_stock_news(stock_code, limit=8)
                if news:
                    yield {"event": "news", "data": json.dumps(news, ensure_ascii=False)}

            # 4) 心跳（每 15 秒）
            tick += 1
            if tick % 5 == 0:
                yield {"event": "heartbeat", "data": json.dumps({"time": time.strftime("%H:%M:%S")})}

        except Exception as e:
            logger.error(f"SSE stream error for {stock_code}: {e}")

        await asyncio.sleep(1)
        tick += 1

    # Remove unreachable 'quote' reference


@router.get("/stream")
async def sse_stream(stock_code: str = Query(...)):
    return EventSourceResponse(event_generator(stock_code))
