"""一键推荐引擎——集全市场数据，调用 DeepSeek AI 生成智能推荐。"""

import json
import logging
import time
from typing import Optional

from app.config import config
from app.services.data_service import data_service
from app.utils.prompt_builder import build_recommendation_prompt
from app.utils.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

# 推荐结果缓存期（秒）
RECOMMEND_CACHE_TTL = 120


class RecommendationService:
    """AI 股票推荐服务——汇总市场全景数据，交给 DeepSeek 深度分析并推荐标的。"""

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

    async def get_recommendations(self, force_refresh: bool = False) -> dict:
        """获取 AI 推荐结果——带频率控制和缓存。"""
        if not force_refresh and not rate_limiter.check("recommend:ai", interval_sec=120):
            # 返回过期缓存
            from app.services.cache_service import cache_service
            cached = cache_service.get("recommend:result")
            if cached:
                cached["cached"] = True
                return cached

        if not config.DEEPSEEK_API_KEY:
            return {
                "error": "请在 .env 中配置 DEEPSEEK_API_KEY",
                "market_assessment": "API Key 未配置",
                "recommendations": [],
            }

        try:
            # 采集全市场数据
            market_data = data_service.get_all_market_data()

            # 构造 prompt
            prompt = build_recommendation_prompt(market_data)

            # 调用 DeepSeek
            response = self.client.chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位管理百亿规模的顶级量化基金经理。你精通：①多因子选股模型（动量/资金/板块/估值/事件/风控六因子）②宏观经济周期分析③行业轮动策略④行为金融学⑤风险管理。你的选股逻辑严谨、评分客观、组合构建科学。输出必须是合法的JSON格式。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=3072,
            )

            raw = response.choices[0].message.content
            result = self._parse_json(raw)

            # 处理推荐列表
            recs = result.get("recommendations", [])
            # 为每只推荐股票补充实时行情
            enriched = []
            for r in recs:
                code = r.get("code", "")
                quote = data_service.get_realtime_quote(code)
                if quote:
                    r["current_price"] = quote["price"]
                    r["current_change"] = quote["change_pct"]
                else:
                    r["current_price"] = r.get("price", 0)
                    r["current_change"] = 0
                enriched.append(r)

            result["recommendations"] = enriched
            result["cached"] = False
            result["generated_at"] = time.strftime("%H:%M:%S")
            result["token_usage"] = response.usage.total_tokens if response.usage else 0

            # 缓存
            from app.services.cache_service import cache_service
            cache_service.set("recommend:result", result, ttl=RECOMMEND_CACHE_TTL)

            return result

        except Exception as e:
            logger.error(f"Recommendation error: {e}")
            return {
                "error": f"AI分析暂时不可用: {str(e)[:100]}",
                "market_assessment": "系统繁忙，请稍后重试",
                "recommendations": [],
            }

    async def get_beginner_content(self, topic: str) -> dict:
        """获取炒股入门教学内容。"""
        cache_key = f"beginner:{topic}"
        from app.services.cache_service import cache_service
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        if not config.DEEPSEEK_API_KEY:
            return {"error": "API Key 未配置"}

        try:
            from app.utils.prompt_builder import build_beginner_guide_prompt
            prompt = build_beginner_guide_prompt(topic)

            response = self.client.chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": "你是一位资深的A股投资者教育专家，输出合法JSON格式。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
            )

            result = self._parse_json(response.choices[0].message.content)
            cache_service.set(cache_key, result, ttl=3600)
            return result

        except Exception as e:
            logger.error(f"Beginner content error: {e}")
            return {"error": f"生成失败: {str(e)[:100]}"}

    async def get_market_snapshot(self) -> dict:
        """获取市场快照——不需要 AI 的纯数据聚合。"""
        return {
            "indices": data_service.get_market_overview(),
            "top_gainers": data_service.get_top_gainers(10),
            "sectors": data_service.get_sector_performance()[:8],
            "concepts": data_service.get_concept_performance()[:6],
            "north_flow": data_service.get_north_flow(),
            "limit_up_count": len(data_service.get_limit_up_pool()),
            "market_time": time.strftime("%Y-%m-%d %H:%M"),
        }

    @staticmethod
    def _parse_json(text: str) -> dict:
        """解析 AI 返回的 JSON。"""
        try:
            text = text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:] if lines else [])
                if text.endswith("```"):
                    text = text[:-3]
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return {
                "market_assessment": "解析失败",
                "recommendations": [],
                "error": "AI响应格式错误",
            }


recommendation_service = RecommendationService()
