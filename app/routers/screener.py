"""条件选股器路由。"""
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

templates_dir = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)), auto_reload=True)
router = APIRouter()


@router.get("/screener", response_class=HTMLResponse)
async def screener_page():
    return HTMLResponse(_jinja_env.get_template("screener.html").render({"active_tab": "screener"}))


@router.get("/api/screener/run")
async def run_screener(
    max_price: float = Query(default=0, description="股价上限"),
    min_price: float = Query(default=0, description="股价下限"),
    max_pe: float = Query(default=0, description="PE上限"),
    min_change: float = Query(default=-100, description="最低涨跌幅%"),
    max_change: float = Query(default=100, description="最高涨跌幅%"),
    min_turnover: float = Query(default=0, description="最低换手率%"),
    max_turnover: float = Query(default=0, description="最高换手率%"),
    sort_by: str = Query(default="change", description="排序: change/price/pe/turnover"),
    limit: int = Query(default=30, le=50),
):
    """多条件选股器——从股池中筛选匹配的股票。"""
    from app.services.data_service import data_service
    from app.services.stock_reference import POPULAR_STOCKS, BUDGET_STOCKS

    # 合并股池
    seen = set()
    all_stocks = []
    for code, name in list(BUDGET_STOCKS) + list(POPULAR_STOCKS):
        if code not in seen:
            seen.add(code)
            all_stocks.append(code)

    quotes = data_service.get_batch_quotes(all_stocks[:120])

    results = []
    for code, q in quotes.items():
        price = q.get("price", 0)
        if price <= 0:
            continue
        change = q.get("change_pct", 0)
        turnover = q.get("turnover", 0)
        pe = q.get("pe", 0)

        if max_price > 0 and price > max_price:
            continue
        if min_price > 0 and price < min_price:
            continue
        if max_pe > 0 and pe > max_pe:
            continue
        if change < min_change or change > max_change:
            continue
        if min_turnover > 0 and turnover < min_turnover:
            continue
        if max_turnover > 0 and turnover > max_turnover:
            continue

        results.append({
            "code": code,
            "name": q["name"],
            "price": round(price, 2),
            "change_pct": round(change, 2),
            "turnover": round(turnover, 2),
            "pe": round(pe, 1),
            "volume": q.get("volume", 0),
            "lot_cost": round(price * 100, 0),
        })

    # 排序
    key_map = {"change": "change_pct", "price": "price", "pe": "pe", "turnover": "turnover"}
    sort_key = key_map.get(sort_by, "change_pct")
    reverse = sort_key in ("change_pct", "turnover")
    results.sort(key=lambda x: abs(x.get(sort_key, 0)), reverse=reverse)

    return {"results": results[:limit], "total": len(results)}
