"""历史记录 & 持仓诊断路由。"""
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

templates_dir = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)), auto_reload=True)
router = APIRouter()


@router.get("/history", response_class=HTMLResponse)
async def history_page():
    return HTMLResponse(_jinja_env.get_template("history.html").render({"active_tab": "history"}))


@router.get("/api/history/list")
async def list_history(limit: int = 20):
    """获取历史分析记录。"""
    from app.models.database import SessionLocal
    from app.models.analysis_log import AnalysisLog
    import json

    db = SessionLocal()
    try:
        logs = db.query(AnalysisLog).order_by(AnalysisLog.created_at.desc()).limit(limit).all()
        results = []
        for log in logs:
            item = {
                "id": log.id,
                "stock_code": log.stock_code,
                "stock_name": log.stock_name,
                "analysis_type": log.analysis_type,
                "price": log.price,
                "change_pct": log.change_pct,
                "ai_summary": log.ai_summary,
                "ai_sentiment": log.ai_sentiment,
                "created_at": str(log.created_at) if log.created_at else "",
                "token_usage": log.token_usage,
            }
            # 如果是portfolio类型，尝试解析summary中的持仓信息
            if log.analysis_type == "portfolio" and log.raw_response:
                try:
                    raw = json.loads(log.raw_response)
                    item["market_judgment"] = raw.get("market_judgment", "")
                    item["positions"] = raw.get("positions", [])
                except Exception:
                    pass
            results.append(item)
        return {"items": results}
    finally:
        db.close()


@router.get("/api/portfolio/audit")
async def audit_portfolio(
    holdings: str = Query(default="", description="持仓JSON: [{code:'000001',shares:1000,entry:10.5},...]"),
):
    """持仓诊断——输入当前持仓，AI分析质量并给出调仓建议。"""
    from app.config import config
    if not config.DEEPSEEK_API_KEY:
        return {"error": "请配置 DEEPSEEK_API_KEY"}

    import json
    try:
        positions = json.loads(holdings) if holdings else []
    except json.JSONDecodeError:
        return {"error": "持仓数据格式错误，请使用JSON格式"}

    if not positions:
        return {"error": "请输入持仓数据"}

    from app.services.data_service import data_service
    from app.services.technical_indicators import comprehensive_analysis

    # 获取每只持仓的实时数据
    codes = [p["code"] for p in positions if p.get("code")]
    quotes = data_service.get_batch_quotes(codes)
    indices = data_service.get_market_overview()

    # 构建持仓分析摘要
    holdings_summary = ""
    total_value = 0
    total_pnl = 0
    for p in positions:
        code = p.get("code", "")
        q = quotes.get(code, {})
        price = q.get("price", 0)
        shares = p.get("shares", 0)
        entry = p.get("entry", price)
        value = price * shares
        pnl = (price - entry) * shares
        pnl_pct = (price - entry) / entry * 100 if entry else 0
        total_value += value
        total_pnl += pnl
        holdings_summary += f"{q.get('name',code)}({code}): 持仓{shares}股 现价{price:.2f} 成本{entry:.2f} 盈亏{pnl:+.0f}元({pnl_pct:+.1f}%) 今日涨跌{q.get('change_pct',0):+.2f}%\n"

    # 市场数据
    idx_str = ""
    for name, idx in indices.items():
        arrow = "↑" if idx["change_pct"] >= 0 else "↓"
        idx_str += f"{name}: {idx['price']:.2f} {arrow}{abs(idx['change_pct']):.2f}%\n"

    prompt = f"""你是A股持仓诊断专家。请分析以下持仓组合并给出调仓建议。

## 大盘环境
{idx_str}

## 当前持仓
{holdings_summary}
总市值: {total_value:.0f}元 | 总盈亏: {total_pnl:+.0f}元

## 要求
1. 评估每只股票的质量（持有/减仓/加仓/清仓）
2. 如果建议卖出，给出卖出股数和理由
3. 如果建议买入新股，必须给出具体代码和买入股数
4. 所有建议必须考虑A股100股/手的交易规则

JSON格式输出：
{{"overall_score":"优秀|良好|一般|较差","summary":"整体评价(60字)","total_value":{total_value:.0f},"total_pnl":{total_pnl:.0f},"actions":[{{"code":"000001","name":"股票名","action":"持有|加仓|减仓|清仓","reason":"理由(30字)","suggested_shares":0,"urgency":"高|中|低"}}],"new_buys":[{{"code":"000001","name":"","price":0,"reason":"推荐理由","suggested_shares":0,"max_price":0}}],"risk_warning":"风险提示"}}"""

    try:
        from app.services.ai_service import ai_service
        resp = ai_service.client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[{"role": "system", "content": "你是A股持仓诊断专家，输出合法JSON。"}, {"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=2048,
        )
        result = json.loads(resp.choices[0].message.content.strip().strip("```json").strip("```").strip())
        result["holdings_analyzed"] = len(positions)
        result["generated_at"] = __import__("time").strftime("%H:%M:%S")
        return result
    except Exception as e:
        return {"error": f"诊断失败: {str(e)[:100]}", "overall_score": "无法评估"}
