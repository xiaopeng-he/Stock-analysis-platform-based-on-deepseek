"""AI 分析服务——调用 DeepSeek API 进行股票分析。"""

import json
import logging
from typing import Optional

from app.services.data_service import data_service
from app.utils.prompt_builder import build_analysis_prompt
from app.utils.rate_limiter import rate_limiter
from app.config import config

logger = logging.getLogger(__name__)


class AIService:
    """DeepSeek API 分析服务——构造 prompt、调用 API、解析结果、记录历史。"""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=config.DEEPSEEK_API_KEY,
                base_url=config.DEEPSEEK_BASE_URL,
            )
        return self._client

    async def analyze_stock(self, stock_code: str, quote: Optional[dict] = None) -> Optional[dict]:
        """对指定股票执行 AI 分析，返回结构化结果。"""
        # 频率控制
        if not rate_limiter.check(f"ai:{stock_code}", interval_sec=60):
            return None

        if not config.DEEPSEEK_API_KEY:
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "summary": "请先在 .env 文件中配置 DEEPSEEK_API_KEY",
                "key_points": [],
                "risk_warning": "API Key 未配置",
            }

        try:
            # 获取数据
            if quote is None:
                quote = data_service.get_realtime_quote(stock_code)

            klines = data_service.get_minute_kline(stock_code, period="5")
            news = data_service.get_stock_news(stock_code, limit=5)

            stock_name = quote.get("name", stock_code) if quote else stock_code

            # 计算技术指标
            from app.services.technical_indicators import comprehensive_analysis
            indicators = comprehensive_analysis(klines) if klines else None

            # 构造 prompt（含技术指标）
            prompt = build_analysis_prompt(
                stock_code, stock_name, quote, klines, news,
                technical_indicators=indicators,
            )

            # 调用 DeepSeek API
            response = self.client.chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位拥有15年实战经验的A股量化分析师。你精通：①技术分析（MACD/KDJ/RSI/布林带/均线/量价关系）②行为金融学（市场情绪、羊群效应、过度反应）③A股博弈逻辑（政策市、板块轮动、主力资金）。你的分析必须基于数据、严谨客观、有可操作性。输出必须是合法JSON格式。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )

            # 解析响应
            raw_text = response.choices[0].message.content
            result = self._parse_response(raw_text)

            # 记录分析到数据库（同步调用，不阻塞）
            self._save_log(
                stock_code=stock_code,
                stock_name=stock_name,
                quote=quote,
                result=result,
                raw=raw_text,
                token_usage=response.usage.total_tokens if response.usage else 0,
            )

            return result

        except Exception as e:
            logger.error(f"DeepSeek API error for {stock_code}: {e}")
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "summary": f"AI分析暂时不可用，请稍后重试",
                "key_points": [],
                "risk_warning": f"API 调用异常",
            }

    def _parse_response(self, text: str) -> dict:
        """解析 DeepSeek 的 JSON 响应，兼容 markdown 代码块包裹。"""
        try:
            # 去除可能的 markdown 包裹
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "sentiment": "neutral",
                "confidence": 0.5,
                "summary": text[:300] if text else "分析结果解析失败",
                "key_points": [],
                "risk_warning": "",
            }

    def _save_log(self, stock_code: str, stock_name: str, quote: Optional[dict], result: dict, raw: str, token_usage: int):
        """保存分析历史到数据库。"""
        try:
            from app.models.database import SessionLocal
            from app.models.analysis_log import AnalysisLog

            db = SessionLocal()
            log = AnalysisLog(
                stock_code=stock_code,
                stock_name=stock_name,
                analysis_type="realtime",
                price=quote.get("price") if quote else None,
                change_pct=quote.get("change_pct") if quote else None,
                ai_summary=result.get("summary", ""),
                ai_sentiment=result.get("sentiment", "neutral"),
                ai_confidence=result.get("confidence", 0.5),
                raw_response=raw,
                token_usage=token_usage,
            )
            db.add(log)
            db.commit()
            db.close()
        except Exception as e:
            logger.warning(f"Failed to save analysis log: {e}")


ai_service = AIService()
