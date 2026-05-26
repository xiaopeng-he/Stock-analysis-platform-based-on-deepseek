"""智能投资组合引擎——基于底仓金额和风险偏好的全自动资产配置。"""

import json
import logging
import time
from typing import Optional

from app.config import config
from app.services.data_service import data_service
from app.utils.prompt_builder import build_portfolio_prompt
from app.utils.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

# 建议的持仓手数映射（A股以100股=1手为单位）
LOT_SIZE = 100


def round_to_lot(shares: int) -> int:
    """将股数取整到手的整数倍。"""
    return max(100, (shares // LOT_SIZE) * LOT_SIZE)


class PortfolioService:
    """智能投资组合服务。"""

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

    async def build_portfolio(self, capital: float, risk_profile: str, max_price: float = 0) -> dict:
        """构建完整的投资组合方案。max_price=单股价上限，0=不限。"""
        if not config.DEEPSEEK_API_KEY:
            return {"error": "请配置 DEEPSEEK_API_KEY"}

        if capital < 1000:
            return {"error": "底仓金额至少1000元"}

        # 验证 max_price 合理性
        if max_price > 0 and max_price * 100 > capital:
            return {"error": f"单股价{max_price}元×100股={max_price*100:.0f}元/手 > 总资金{capital:.0f}元，买不起！请降低上限或增加资金"}

        valid_profiles = ["保守", "稳健", "进取"]
        if risk_profile not in valid_profiles:
            risk_profile = "稳健"

        cache_tag = f"portfolio:{risk_profile}:{capital:.0f}:{max_price:.0f}"
        # 频率控制
        if not rate_limiter.check(cache_tag, interval_sec=90):
            from app.services.cache_service import cache_service
            cached = cache_service.get(cache_tag)
            if cached:
                cached["cached"] = True
                return cached

        try:
            # ── v0.6: 用腾讯API构建真实候选池 ──
            from app.services.stock_reference import POPULAR_STOCKS, BUDGET_STOCKS
            from app.services.cache_service import cache_service as _cs

            # 1) 大盘指数
            indices = data_service.get_market_overview()

            # 2) 候选股池：优先用低价股池，大资金合并热门股池
            if max_price > 0 and max_price <= 20:
                # 小资金/低单价：优先低价股池
                all_candidates = list(BUDGET_STOCKS) + list(POPULAR_STOCKS)
            else:
                all_candidates = list(POPULAR_STOCKS) + list(BUDGET_STOCKS)

            # 去重
            seen = set()
            unique_candidates = []
            for code, name in all_candidates:
                if code not in seen:
                    seen.add(code)
                    unique_candidates.append((code, name))

            # 按max_price粗筛
            pre_filtered = []
            for code, name in unique_candidates:
                if max_price > 0:
                    cached = _cs.get(f"quote:{code}")
                    if cached and cached.get("price", 99999) > max_price:
                        continue
                pre_filtered.append(code)

            # 批量获取实时行情
            all_quotes = data_service.get_batch_quotes(pre_filtered[:80])

            for code, q in all_quotes.items():
                price = q.get("price", 0)
                if price <= 0:
                    continue
                if max_price > 0 and price > max_price:
                    continue  # 超过单股价上限，剔除
                lot_cost = price * 100
                if lot_cost > capital * 0.25:
                    continue  # 1手超过25%总资金，买不起
                candidates.append({
                    "code": code,
                    "name": q["name"],
                    "price": price,
                    "change_pct": q.get("change_pct", 0),
                    "turnover": q.get("turnover", 0),
                    "pe": q.get("pe", 0),
                })

            # 按涨跌幅排序取前30
            candidates.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
            candidates = candidates[:30]

            # 3) 构建 market_data——只用真实数据
            from app.services.scheduler_service import get_trading_status
            market_data = {
                "indices": indices,
                "top_gainers": candidates,
                "top_losers": [],
                "sectors": data_service.get_sector_performance(),
                "concepts": data_service.get_concept_performance(),
                "north_flow": data_service.get_north_flow(),
                "limit_up": [],
                "market_news": data_service.get_market_news(5),
                "market_time": time.strftime("%Y-%m-%d %H:%M"),
                "candidate_count": len(candidates),
            }

            # 如果没有候选股，直接返回错误
            if not candidates:
                max_info = f"且单价≤{max_price}元" if max_price > 0 else ""
                return {"error": f"当前没有符合条件的股票（资金{capital:.0f}元{max_info}）。建议降低单股价上限或增加资金。"}

            # 构造 Prompt
            prompt = build_portfolio_prompt(market_data, capital, risk_profile, max_price)

            # 调用 DeepSeek
            response = self.client.chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "你是一位管理百亿规模的CIO(首席投资官)，拥有20年A股实战经验。你精通现代投资组合理论(Markowitz)、风险预算(Risk Budgeting)、凯利公式(Kelly Criterion)和行为金融学。你的投资方案科学严谨、风险可控、可执行。输出必须是合法JSON格式。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=3072,
            )

            raw = response.choices[0].message.content
            result = self._parse(raw)

            # ── 关键后处理：验证和修正资金可行性 ──
            if result.get("positions"):
                codes = [p["code"] for p in result["positions"] if p.get("code")]
                quotes = data_service.get_batch_quotes(codes) if codes else {}

                valid_positions = []
                total_allocated = 0

                for pos in result["positions"]:
                    code = pos.get("code", "")
                    q = quotes.get(code)
                    if not q:
                        continue  # 拿不到实时行情就跳过

                    price = q["price"]
                    # 如果设置了单股价上限且超出，直接跳过
                    if max_price > 0 and price > max_price:
                        continue
                    lot_cost = price * 100  # 1手=100股

                    # 修正价格
                    pos["current_price"] = price
                    pos["current_change"] = q["change_pct"]

                    # 根据资金重新计算可买股数
                    alloc_amount = pos.get("allocation_amount", 0)
                    if alloc_amount <= 0:
                        alloc_pct = pos.get("allocation_pct", 10)
                        alloc_amount = capital * alloc_pct / 100

                    # ⚠️ 关键：验证是否买得起至少1手
                    if lot_cost > alloc_amount:
                        # 买不起——调整分配额为1手成本
                        alloc_amount = lot_cost
                        pos["allocation_amount"] = lot_cost
                        pos["allocation_pct"] = round(lot_cost / capital * 100, 1)

                    # ⚠️ 关键：确保不超总资金
                    if total_allocated + alloc_amount > capital:
                        alloc_amount = max(lot_cost, capital - total_allocated)
                        pos["allocation_amount"] = alloc_amount
                        pos["allocation_pct"] = round(alloc_amount / capital * 100, 1)

                    # 计算可买手数
                    max_lots = int(alloc_amount / lot_cost)
                    if max_lots < 1:
                        continue  # 实在买不起就跳过

                    # 只买1手的倍数
                    suggested_lots = max(1, min(max_lots, int(alloc_amount * 0.95 / lot_cost)))
                    shares = suggested_lots * 100
                    actual_cost = shares * price

                    # ⚠️ 最终验证：实际成本不超分配额
                    if actual_cost > alloc_amount * 1.2:
                        shares = max(100, int(alloc_amount / price / 100) * 100)
                        actual_cost = shares * price

                    pos["suggested_shares"] = shares
                    pos["actual_cost"] = actual_cost
                    pos["allocation_amount"] = actual_cost
                    pos["allocation_pct"] = round(actual_cost / capital * 100, 1)
                    pos["lot_cost"] = lot_cost
                    pos["lots"] = shares // 100

                    total_allocated += actual_cost
                    valid_positions.append(pos)

                # 替换为验证通过的持仓
                result["positions"] = valid_positions

                # 修正资金分配总结
                cash = capital - total_allocated
                result["allocation"] = {
                    "total_capital": capital,
                    "invested_amount": total_allocated,
                    "cash_reserve": max(0, cash),
                    "cash_reserve_pct": round(max(0, cash) / capital * 100, 1),
                    "expected_return": result.get("allocation", {}).get("expected_return", "视市场而定"),
                    "max_drawdown_estimate": result.get("allocation", {}).get("max_drawdown_estimate", "视持仓而定"),
                }

                # 如果验证后没有任何可行的持仓
                if not valid_positions:
                    result["error"] = f"资金{capital:.0f}元不足以购买任何推荐股票（每只需要至少1手=100股）。建议增加资金或选择单价更低的标的。"
                    result["positions"] = []

            result["generated_at"] = time.strftime("%H:%M:%S")
            result["token_usage"] = response.usage.total_tokens if response.usage else 0
            result["risk_profile"] = risk_profile
            result["capital"] = capital

            # 保存到数据库
            try:
                from app.models.database import SessionLocal
                from app.models.analysis_log import AnalysisLog
                db = SessionLocal()
                log = AnalysisLog(
                    stock_code="PORTFOLIO",
                    stock_name=f"{risk_profile}型组合 {capital:.0f}元",
                    analysis_type="portfolio",
                    price=capital,
                    ai_summary=json.dumps(result.get("positions", [])[:5], ensure_ascii=False),
                    ai_sentiment=risk_profile,
                    raw_response=json.dumps(result, ensure_ascii=False),
                    token_usage=response.usage.total_tokens if response.usage else 0,
                )
                db.add(log)
                db.commit()
                db.close()
            except Exception as e:
                logger.warning(f"Failed to save portfolio: {e}")

            # 缓存
            from app.services.cache_service import cache_service
            cache_service.set(cache_tag, result, ttl=120)

            return result

        except Exception as e:
            logger.error(f"Portfolio build error: {e}")
            return {"error": f"组合构建失败: {str(e)[:100]}"}

    @staticmethod
    def _parse(text: str) -> dict:
        try:
            text = text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:])
                if text.endswith("```"):
                    text = text[:-3]
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return {"error": "AI响应格式异常", "positions": []}


portfolio_service = PortfolioService()
