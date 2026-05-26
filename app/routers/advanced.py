"""高级功能路由——风险分析、交易日志、自然语言选股、专业报告、提醒。"""
import json, time
from fastapi import APIRouter, Query

router = APIRouter()


# ═══════════════ 风险分析 ═══════════════
@router.get("/api/risk/{stock_code}")
async def stock_risk(stock_code: str):
    """个股综合风险报告。"""
    from app.services.data_service import data_service
    from app.services.risk_service import comprehensive_risk_report

    klines = data_service.get_daily_kline(stock_code) or data_service.get_minute_kline(stock_code, "60")
    if not klines or len(klines) < 10:
        return {"error": "数据不足"}

    closes = [k["close"] for k in klines]
    # 尝试获取指数数据做对比
    idx_klines = data_service.get_daily_kline("000001") or []
    idx_closes = [k["close"] for k in idx_klines] if idx_klines else None

    report = comprehensive_risk_report(stock_code, closes, idx_closes)
    quote = data_service.get_realtime_quote(stock_code)
    report["name"] = quote["name"] if quote else stock_code
    report["price"] = quote["price"] if quote else closes[-1]
    return report


@router.get("/api/risk/portfolio-correlation")
async def portfolio_correlation(codes: str = Query(default="")):
    """计算组合内股票间的相关系数矩阵。"""
    from app.services.data_service import data_service
    from app.services.risk_service import calc_correlation

    code_list = [c.strip() for c in codes.split(",") if c.strip()][:8]
    if len(code_list) < 2:
        return {"error": "至少需要2只股票"}

    # 获取日K线
    price_data = {}
    names = {}
    for code in code_list:
        klines = data_service.get_daily_kline(code) or data_service.get_minute_kline(code, "60")
        if klines and len(klines) >= 10:
            price_data[code] = [k["close"] for k in klines]
            q = data_service.get_realtime_quote(code)
            names[code] = q["name"] if q else code

    matrix = []
    warnings = []
    for i, c1 in enumerate(code_list):
        row = {"code": c1, "name": names.get(c1, c1), "correlations": []}
        for j, c2 in enumerate(code_list):
            if c1 in price_data and c2 in price_data and i != j:
                corr = calc_correlation(price_data[c1], price_data[c2])
                val = corr["correlation"]
                row["correlations"].append({"code": c2, "name": names.get(c2, c2), "correlation": val, "level": corr["level"]})
                if val > 0.7:
                    warnings.append(f"⚠ {names.get(c1,c1)} 与 {names.get(c2,c2)} 高度正相关({val:.2f})，分散效果差")
        matrix.append(row)

    return {"matrix": matrix, "warnings": list(set(warnings))}


# ═══════════════ 交易日志 ═══════════════
@router.post("/api/trade/log")
async def add_trade_log(data: dict):
    """记录一笔交易。"""
    from app.models.database import SessionLocal
    from app.models.trade_log import TradeLog

    db = SessionLocal()
    try:
        log = TradeLog(
            stock_code=data.get("code", ""),
            stock_name=data.get("name", ""),
            action=data.get("action", "买入"),
            price=data.get("price", 0),
            shares=data.get("shares", 0),
            amount=data.get("amount", data.get("price", 0) * data.get("shares", 0)),
            reason=data.get("reason", ""),
            emotion=data.get("emotion", "理性"),
            mistake_type=data.get("mistake_type", ""),
        )
        db.add(log)
        db.commit()
        return {"ok": True, "id": log.id}
    finally:
        db.close()


@router.get("/api/trade/logs")
async def list_trade_logs(limit: int = 30):
    """交易日志列表。"""
    from app.models.database import SessionLocal
    from app.models.trade_log import TradeLog

    db = SessionLocal()
    try:
        logs = db.query(TradeLog).order_by(TradeLog.created_at.desc()).limit(limit).all()
        return {"logs": [{"id": l.id, "code": l.stock_code, "name": l.stock_name, "action": l.action,
                          "price": l.price, "shares": l.shares, "amount": l.amount,
                          "reason": l.reason, "emotion": l.emotion, "mistake_type": l.mistake_type,
                          "pnl": l.result_pnl, "reviewed": l.reviewed,
                          "created_at": str(l.created_at) if l.created_at else ""} for l in logs]}
    finally:
        db.close()


@router.put("/api/trade/{trade_id}/review")
async def review_trade(trade_id: int, data: dict):
    """复盘一笔交易。"""
    from app.models.database import SessionLocal
    from app.models.trade_log import TradeLog

    db = SessionLocal()
    try:
        log = db.query(TradeLog).filter_by(id=trade_id).first()
        if log:
            log.reviewed = 1
            log.review_notes = data.get("notes", "")
            log.mistake_type = data.get("mistake_type", log.mistake_type)
            log.lesson = data.get("lesson", "")
            log.result_pnl = data.get("pnl", log.result_pnl)
            db.commit()
        return {"ok": True}
    finally:
        db.close()


@router.get("/api/trade/summary")
async def trade_summary():
    """交易统计——胜率、盈亏比、常见错误。"""
    from app.models.database import SessionLocal
    from app.models.trade_log import TradeLog

    db = SessionLocal()
    try:
        logs = db.query(TradeLog).order_by(TradeLog.created_at.desc()).all()
        total = len(logs)
        if not total:
            return {"total_trades": 0}

        buys = [l for l in logs if l.action == "买入"]
        sells = [l for l in logs if l.action == "卖出"]
        pnl_total = sum(l.result_pnl or 0 for l in logs)
        win_count = sum(1 for l in logs if (l.result_pnl or 0) > 0)
        mistake_counts = {}
        for l in logs:
            if l.mistake_type and l.mistake_type != "无":
                mistake_counts[l.mistake_type] = mistake_counts.get(l.mistake_type, 0) + 1
        emotion_counts = {}
        for l in logs:
            if l.emotion:
                emotion_counts[l.emotion] = emotion_counts.get(l.emotion, 0) + 1

        return {
            "total_trades": total,
            "buys": len(buys),
            "sells": len(sells),
            "total_pnl": round(pnl_total, 2),
            "win_rate": round(win_count / total * 100, 1) if total else 0,
            "avg_pnl_per_trade": round(pnl_total / total, 2) if total else 0,
            "top_mistakes": sorted(mistake_counts.items(), key=lambda x: x[1], reverse=True)[:5],
            "emotions": emotion_counts,
        }
    finally:
        db.close()


# ═══════════════ 自然语言选股 ═══════════════
@router.get("/api/screener/nl")
async def natural_language_screener(q: str = Query(default="")):
    """自然语言选股——AI解析用户描述转换为筛选条件。"""
    from app.config import config
    if not q or not config.DEEPSEEK_API_KEY:
        return {"error": "请输入选股条件描述"}

    prompt = f"""用户用自然语言描述了选股条件，请将其转化为具体的筛选参数。

用户描述: "{q}"

请解析并输出JSON格式的筛选参数:
{{"max_price":0,"min_price":0,"max_pe":0,"min_change":-100,"max_change":100,"min_turnover":0,"explanation":"你理解的条件(30字)"}}

例如用户说"找股息高、负债低、现金流好的低价股"→ max_price=15, explanation="筛选15元以下的基本面稳健股"
用户说"找最近涨得好的科技股"→ min_change=3, explanation="筛选近期涨幅超3%的强势股"
用户说"找PE低于20的银行股"→ max_pe=20, max_price=10, explanation="筛选低估值银行股" """

    try:
        from app.services.ai_service import ai_service
        resp = ai_service.client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=300,
        )
        result = json.loads(resp.choices[0].message.content.strip().strip("```json").strip("```").strip())
        return result
    except Exception as e:
        return {"error": f"解析失败: {str(e)[:80]}", "max_price": 0}


# ═══════════════ 报告生成 ═══════════════
@router.get("/api/report/stock/{stock_code}")
async def stock_report(stock_code: str, style: str = "pro"):
    """个股分析报告——专业版/新手版。"""
    from app.services.data_service import data_service
    from app.services.technical_indicators import comprehensive_analysis
    from app.services.risk_service import comprehensive_risk_report

    quote = data_service.get_realtime_quote(stock_code)
    if not quote:
        return {"error": "未找到该股票"}

    klines = data_service.get_daily_kline(stock_code) or data_service.get_minute_kline(stock_code, "60")
    indicators = comprehensive_analysis(klines) if klines and len(klines) >= 10 else None
    risk = comprehensive_risk_report(stock_code, [k["close"] for k in klines]) if klines else {}
    news = data_service.get_stock_news(stock_code, 5)
    indices = data_service.get_market_overview()

    return {
        "stock": {"code": stock_code, "name": quote["name"], "price": quote["price"], "change_pct": quote["change_pct"]},
        "indicators": {
            "trend": indicators["trend_summary"]["overall"] if indicators else "N/A",
            "rsi": indicators["rsi"]["rsi_current"] if indicators else None,
            "macd": indicators["macd"]["signal"] if indicators else "N/A",
            "kdj": indicators["kdj"]["signal"] if indicators else "N/A",
        } if indicators else {},
        "risk": risk,
        "news": news[:5],
        "market": indices,
        "style": style,
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
    }


@router.get("/report/{stock_code}")
async def report_page(stock_code: str):
    """个股分析报告HTML页面（可打印）"""
    from fastapi.responses import HTMLResponse
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path

    from app.services.data_service import data_service
    from app.services.technical_indicators import comprehensive_analysis
    from app.services.risk_service import comprehensive_risk_report

    quote = data_service.get_realtime_quote(stock_code)
    if not quote:
        return HTMLResponse("<h2>股票未找到</h2>")

    klines = data_service.get_daily_kline(stock_code) or data_service.get_minute_kline(stock_code, "60")
    closes = [k["close"] for k in klines] if klines else []
    indicators = comprehensive_analysis(klines) if klines and len(klines) >= 10 else {}
    risk = comprehensive_risk_report(stock_code, closes) if closes else {}
    news = data_service.get_stock_news(stock_code, 5)

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><title>{quote['name']} 分析报告</title>
<style>body{{font-family:'Noto Sans SC',sans-serif;max-width:800px;margin:0 auto;padding:20px;color:#1a1a1a;line-height:1.8}}
h1{{border-bottom:3px solid #3b82f6;padding-bottom:8px}}h2{{color:#3b82f6;margin-top:24px}}table{{width:100%;border-collapse:collapse;margin:10px 0}}td,th{{border:1px solid #ddd;padding:8px 12px;text-align:center}}th{{background:#f5f5f5}}
.up{{color:#ec5a5a}}.down{{color:#47b262}}.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600}}
.badge-green{{background:#e6f7ee;color:#47b262}}.badge-red{{background:#fde8e8;color:#ec5a5a}}.badge-yellow{{background:#fef3c7;color:#d97706}}
.footer{{margin-top:40px;padding-top:16px;border-top:1px solid #ddd;font-size:12px;color:#999}}
@media print{{body{{font-size:13px}}}}</style></head><body>
<h1>📊 {quote['name']} ({stock_code}) 分析报告</h1>
<p>生成时间: {time.strftime('%Y-%m-%d %H:%M')} | 最新价: <strong>{quote['price']:.2f}元</strong> <span class="{'up' if quote['change_pct']>=0 else 'down'}">{quote['change_pct']:+.2f}%</span></p>
<h2>一、技术指标</h2><table><tr><th>指标</th><th>数值</th><th>信号</th></tr>"""

    ind_data = [
        ("趋势评分", f"{indicators.get('trend_summary',{}).get('strength',0)}分", indicators.get('trend_summary',{}).get('overall','N/A')),
        ("MACD", f"DIF:{indicators.get('macd',{}).get('dif_current',0):.4f}", indicators.get('macd',{}).get('signal','N/A')),
        ("RSI(14)", str(indicators.get('rsi',{}).get('rsi_current','N/A')), indicators.get('rsi',{}).get('signal','N/A')),
        ("KDJ", f"K:{indicators.get('kdj',{}).get('k_current','N/A')}", indicators.get('kdj',{}).get('signal','N/A')),
        ("布林带", f"带宽:{indicators.get('bollinger',{}).get('bandwidth_pct','N/A')}%", indicators.get('bollinger',{}).get('signal','N/A')),
        ("量价", str(indicators.get('volume',{}).get('vol_ratio','N/A')), indicators.get('volume',{}).get('signal','N/A')),
    ]
    for name, val, sig in ind_data:
        html += f"<tr><td>{name}</td><td>{val}</td><td>{sig}</td></tr>"
    html += "</table>"

    html += "<h2>二、风险评估</h2><table><tr><th>指标</th><th>数值</th></tr>"
    risk_data = [
        ("最大回撤", f"{risk.get('max_drawdown',{}).get('mdd_pct',0)}%"),
        ("VaR(95%)", f"{risk.get('var_95',{}).get('var_pct',0)}%"),
        ("年化波动率", f"{risk.get('volatility',{}).get('annual_vol',0)}%"),
        ("夏普比率", str(risk.get('sharpe',{}).get('sharpe','N/A'))),
        ("贝塔系数", f"{risk.get('beta',{}).get('beta','N/A')} ({risk.get('beta',{}).get('interpretation','')})"),
    ]
    for name, val in risk_data:
        html += f"<tr><td>{name}</td><td>{val}</td></tr>"
    html += "</table>"

    html += "<h2>三、压力测试</h2><table><tr><th>情景</th><th>目标价</th><th>亏损</th></tr>"
    for s in risk.get("stress_test", {}).get("scenarios", []):
        html += f"<tr><td>{s['scenario']}</td><td>{s['target_price']:.2f}元</td><td class=\"down\">-{s['loss_pct']}% ({s['loss']:.2f}元)</td></tr>"
    html += "</table>"

    html += "<h2>四、相关新闻</h2><ol>"
    for n in news[:5]:
        html += f"<li>{n.get('title','')} <small>({n.get('source','')} {n.get('time','')})</small></li>"
    html += "</ol>"

    html += """<div class="footer"><p><strong>免责声明</strong>：本报告由AI自动生成，仅供参考，不构成投资建议。股市有风险，投资需谨慎。</p><p>A股智析 · DeepSeek AI 驱动</p></div></body></html>"""
    return HTMLResponse(html)


# ═══════════════ 行业暴露 ═══════════════
@router.get("/api/portfolio/exposure")
async def portfolio_exposure(holdings: str = Query(default="")):
    """持仓行业和风格暴露分析。"""
    try:
        positions = json.loads(holdings) if holdings else []
    except json.JSONDecodeError:
        return {"error": "数据格式错误"}

    if not positions:
        return {"error": "请提供持仓数据"}

    from app.services.data_service import data_service
    codes = [p.get("code", "") for p in positions if p.get("code")]
    quotes = data_service.get_batch_quotes(codes)

    items = []
    for p in positions:
        code = p.get("code", "")
        q = quotes.get(code, {})
        value = q.get("price", 0) * p.get("shares", 0)
        items.append({"code": code, "value": value, "shares": p.get("shares", 0)})

    from app.services.industry_service import analyze_exposure, get_sector_rotation_hint
    exposure = analyze_exposure(items)
    rotation = get_sector_rotation_hint()
    exposure["sector_rotation"] = rotation
    return exposure


# ═══════════════ 每日简报 ═══════════════
@router.get("/api/briefing/daily")
async def daily_briefing():
    """每日市场简报。"""
    from app.services.data_service import data_service
    from app.services.industry_service import get_sector_rotation_hint

    indices = data_service.get_market_overview()
    sectors = data_service.get_sector_performance()[:5]
    rotation = get_sector_rotation_hint()
    news = data_service.get_market_news(6)

    # 计算市场概况
    total_change = 0; count = 0
    for idx in indices.values():
        total_change += idx.get("change_pct", 0); count += 1
    avg = total_change / count if count else 0

    sentiment = "偏暖" if avg > 0.5 else "偏冷" if avg < -0.5 else "震荡"

    return {
        "date": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
        "sentiment": sentiment,
        "indices": indices,
        "avg_change": round(avg, 2),
        "top_sectors": [s["name"] for s in sectors[:5]],
        "sector_rotation": rotation,
        "top_news": news[:6],
        "generated_at": time.strftime("%H:%M:%S"),
    }


# ═══════════════ 索提诺比率 ═══════════════
@router.get("/api/risk/sortino/{stock_code}")
async def sortino_ratio(stock_code: str):
    """索提诺比率——只惩罚下行波动。"""
    from app.services.data_service import data_service

    klines = data_service.get_daily_kline(stock_code) or data_service.get_minute_kline(stock_code, "60")
    if not klines or len(klines) < 20:
        return {"sortino": 0, "note": "数据不足"}

    closes = [k["close"] for k in klines]
    returns = [(closes[i]-closes[i-1])/closes[i-1] for i in range(1, len(closes))]
    total_return = (closes[-1]-closes[0])/closes[0] if closes[0] else 0
    days = len(closes)
    annual_return = (1+total_return)**(252/days)-1 if days>0 else 0

    # 下行偏差
    downside_returns = [r for r in returns if r < 0]
    if not downside_returns:
        return {"sortino": 999, "annual_return": round(annual_return*100,2), "note": "无下行波动(极强)"}

    mean_down = sum(downside_returns)/len(downside_returns)
    variance = sum((r-mean_down)**2 for r in downside_returns)/(len(downside_returns)-1) if len(downside_returns)>1 else 0
    import math
    downside_dev = math.sqrt(variance)*math.sqrt(252)
    sortino = (annual_return-0.02)/downside_dev if downside_dev else 0

    return {"sortino": round(sortino, 2), "annual_return": round(annual_return*100, 2), "downside_dev_annual": round(downside_dev*100, 2)}


# ═══════════════ AI输出难度调节 ═══════════════
@router.get("/api/adjust")
async def adjust_output(content: str = Query(default=""), mode: str = Query(default="simple")):
    """调节AI输出——看不懂→白话 / 更专业 / 只要重点。"""
    from app.config import config
    if not content or not config.DEEPSEEK_API_KEY:
        return {"result": content}

    prompts = {
        "simple": f"请把以下投资分析内容用最简单的大白话重新解释，像给完全不懂股票的朋友讲一样。用生活化的比喻，不要术语:\n\n{content}",
        "pro": f"请把以下内容用更专业的金融术语重写，加入量化分析视角:\n\n{content}",
        "tldr": f"请把以下内容压缩成3句话以内的核心要点:\n\n{content}",
    }

    try:
        from app.services.ai_service import ai_service
        resp = ai_service.client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompts.get(mode, prompts["simple"])}],
            temperature=0.5, max_tokens=500,
        )
        return {"result": resp.choices[0].message.content.strip(), "mode": mode}
    except Exception as e:
        return {"result": content, "error": str(e)[:80]}


# ═══════════════ 一句话总结 ═══════════════
@router.get("/api/stock/{stock_code}/oneliner")
async def stock_oneliner(stock_code: str):
    """每只股票一句话总结。"""
    from app.services.data_service import data_service
    from app.config import config

    quote = data_service.get_realtime_quote(stock_code)
    if not quote:
        return {"oneliner": "未找到该股票"}

    if not config.DEEPSEEK_API_KEY:
        change = quote.get("change_pct", 0)
        if change > 3:
            return {"oneliner": f"{quote['name']}今日大涨{change:+.1f}%，表现强势"}
        elif change > 0:
            return {"oneliner": f"{quote['name']}微涨{change:+.1f}%，走势平稳"}
        elif change > -3:
            return {"oneliner": f"{quote['name']}小跌{change:+.1f}%，正常波动"}
        else:
            return {"oneliner": f"{quote['name']}大跌{change:+.1f}%，注意风险"}

    prompt = f"""{quote['name']}({stock_code}) 现价{quote['price']:.2f}元 涨跌{quote['change_pct']:+.2f}% PE{quote.get('pe',0):.1f}
请用一句大白话(20字以内)告诉新手这只股票今天值不值得关注。JSON格式:{{"oneliner":"一句话"}}"""
    try:
        from app.services.ai_service import ai_service
        resp = ai_service.client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=100,
        )
        result = json.loads(resp.choices[0].message.content.strip().strip("```json").strip("```").strip())
        return result
    except Exception:
        return {"oneliner": f"{quote['name']} {quote['price']:.2f}元 {quote['change_pct']:+.2f}%"}


# ═══════════════ 月度/季度复盘 ═══════════════
@router.get("/api/review/summary")
async def review_summary(period: str = "monthly"):
    """月度/季度/年度复盘总结——基于交易日志。"""
    from app.models.database import SessionLocal
    from app.models.trade_log import TradeLog
    from datetime import datetime, timedelta

    now = datetime.now()
    if period == "monthly":
        since = now - timedelta(days=30)
    elif period == "quarterly":
        since = now - timedelta(days=90)
    else:  # yearly
        since = now - timedelta(days=365)

    db = SessionLocal()
    try:
        logs = db.query(TradeLog).filter(TradeLog.created_at >= since).order_by(TradeLog.created_at).all()
        if not logs:
            return {"period": period, "total_trades": 0, "summary": "该时段无交易记录"}

        total_pnl = sum(l.result_pnl or 0 for l in logs)
        win_count = sum(1 for l in logs if (l.result_pnl or 0) > 0)
        mistake_counts = {}
        for l in logs:
            if l.mistake_type and l.mistake_type != "无":
                mistake_counts[l.mistake_type] = mistake_counts.get(l.mistake_type, 0) + 1

        top_mistake = max(mistake_counts, key=mistake_counts.get) if mistake_counts else "无"
        top_mistake_count = mistake_counts.get(top_mistake, 0)

        return {
            "period": period,
            "date_range": f"{since.strftime('%m/%d')} - {now.strftime('%m/%d')}",
            "total_trades": len(logs),
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(win_count / len(logs) * 100, 1) if logs else 0,
            "top_mistake": f"{top_mistake}({top_mistake_count}次)",
            "summary": f"{period}共交易{len(logs)}笔，{'盈利' if total_pnl>0 else '亏损'}{abs(total_pnl):.0f}元，胜率{win_count/len(logs)*100:.0f}%，最常见错误：{top_mistake}" if logs else "",
        }
    finally:
        db.close()

