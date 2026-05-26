"""股票对比路由——多只股票同屏对比。"""

from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

templates_dir = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)), auto_reload=True)

router = APIRouter()


def _render(name: str, ctx: dict) -> HTMLResponse:
    return HTMLResponse(_jinja_env.get_template(name).render(**ctx))


@router.get("/compare", response_class=HTMLResponse)
async def compare_page():
    return _render("compare.html", {"active_tab": "compare"})


@router.get("/api/compare/data")
async def compare_data(codes: str = Query(default="")):
    """批量获取多只股票数据用于对比。"""
    from app.services.data_service import data_service
    from app.services.technical_indicators import comprehensive_analysis

    code_list = [c.strip() for c in codes.split(",") if c.strip()][:5]
    if not code_list:
        return {"stocks": []}

    quotes = data_service.get_batch_quotes(code_list)
    result = []
    for code in code_list:
        quote = quotes.get(code)
        if not quote:
            continue
        klines = data_service.get_minute_kline(code, period="5")
        indicators = comprehensive_analysis(klines) if klines and len(klines) >= 10 else None

        result.append({
            "code": code,
            "name": quote["name"],
            "price": quote["price"],
            "change_pct": quote["change_pct"],
            "volume": quote["volume"],
            "turnover": quote["turnover"],
            "pe": quote["pe"],
            "trend": indicators["trend_summary"]["overall"] if indicators else "N/A",
            "trend_score": indicators["trend_summary"]["strength"] if indicators else 0,
            "rsi": indicators["rsi"]["rsi_current"] if indicators else None,
            "macd_signal": indicators["macd"]["signal"] if indicators else "N/A",
        })
    return {"stocks": result}
