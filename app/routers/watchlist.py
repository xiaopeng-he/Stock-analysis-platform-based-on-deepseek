"""自选股管理 API 路由。"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path

from app.models.database import SessionLocal, get_db
from app.models.watchlist import WatchlistItem

router = APIRouter()


class AddStockRequest(BaseModel):
    stock_code: str
    stock_name: str
    entry_price: float = 0.0
    shares: int = 0


class UpdatePositionRequest(BaseModel):
    entry_price: float = 0.0
    shares: int = 0
    notes: str = ""


def _get_exchange(code: str) -> str:
    """根据代码前缀判断交易所。"""
    if code.startswith("6"):
        return "SH"
    elif code.startswith(("0", "3")):
        return "SZ"
    elif code.startswith(("4", "8")):
        return "BJ"
    return "SZ"


@router.get("/search")
async def search_stocks(request: Request, keyword: str = ""):
    """搜索股票——返回 HTML 片段用于 HTMX。"""
    if not keyword or len(keyword) < 1:
        return HTMLResponse("<div class='search-empty'>输入关键词搜索</div>")

    from app.services.data_service import data_service

    results = data_service.search_stock(keyword)
    if not results:
        return HTMLResponse("<div class='search-empty'>未找到匹配股票</div>")

    html_parts = ["<div class='search-result-list'>"]
    for r in results:
        html_parts.append(
            f"<div class='search-result-item'>"
            f"<span>{r['name']} ({r['code']})</span>"
            f"<span class='search-price'>{r['price']:.2f}</span>"
            f"<button class='btn btn-sm' "
            f"hx-post='/api/watchlist/add' "
            f"hx-vals='{{\"stock_code\":\"{r['code']}\",\"stock_name\":\"{r['name']}\"}}' "
            f"hx-target='#watchlist-container' "
            f"hx-swap='innerHTML' "
            f"onclick=\"document.getElementById('add-stock-modal').classList.add('hidden')\""
            f">添加</button>"
            f"</div>"
        )
    html_parts.append("</div>")
    return HTMLResponse("".join(html_parts))


@router.post("/watchlist/add")
async def add_to_watchlist(req: AddStockRequest):
    """添加自选股。"""
    db = SessionLocal()
    try:
        existing = db.query(WatchlistItem).filter_by(stock_code=req.stock_code).first()
        if existing:
            existing.is_active = 1
        else:
            item = WatchlistItem(
                stock_code=req.stock_code,
                stock_name=req.stock_name,
                exchange=_get_exchange(req.stock_code),
            )
            db.add(item)
        db.commit()
    finally:
        db.close()

    return await _render_watchlist()


@router.delete("/watchlist/{item_id}")
async def remove_from_watchlist(item_id: int):
    """删除自选股（软删除）。"""
    db = SessionLocal()
    try:
        item = db.query(WatchlistItem).filter_by(id=item_id).first()
        if item:
            item.is_active = 0
            db.commit()
    finally:
        db.close()
    return await _render_watchlist()


@router.put("/watchlist/{stock_code}/position")
async def update_position(stock_code: str, req: UpdatePositionRequest):
    """更新持仓信息——买入价和数量。"""
    db = SessionLocal()
    try:
        item = db.query(WatchlistItem).filter_by(stock_code=stock_code, is_active=1).first()
        if item:
            item.entry_price = req.entry_price
            item.shares = req.shares
            if req.notes is not None:
                item.notes = req.notes
            db.commit()
    finally:
        db.close()
    return {"ok": True}


@router.get("/watchlist/list")
async def list_watchlist(request: Request, sort: str = "default"):
    """获取自选股列表 HTML 片段——支持排序: default/change/name。"""
    return await _render_watchlist(request, sort)


async def _render_watchlist(request: Request = None, sort: str = "default"):
    """渲染自选股列表 HTML。"""
    from app.services.data_service import data_service

    db = SessionLocal()
    try:
        items = db.query(WatchlistItem).filter_by(is_active=1).all()
    finally:
        db.close()

    if not items:
        # 首次使用：自动预置演示自选股
        demo_stocks = [
            ("600519", "贵州茅台"), ("000001", "平安银行"), ("300750", "宁德时代"),
            ("000858", "五粮液"), ("601318", "中国平安"), ("002594", "比亚迪"),
        ]
        for code, name in demo_stocks:
            db = SessionLocal()
            try:
                db.add(WatchlistItem(stock_code=code, stock_name=name, exchange=_get_exchange(code)))
                db.commit()
            finally:
                db.close()
        return await _render_watchlist(request)

    # 只用缓存数据——绝不阻塞页面渲染
    codes = [i.stock_code for i in items]
    from app.services.cache_service import cache_service as _cs
    quotes = {}
    for code in codes:
        cached = _cs.get(f"quote:{code}")
        if cached:
            quotes[code] = cached
    # 如果有缺失，尝试批量补（但超时立即放弃）
    uncached = [c for c in codes if c not in quotes]
    if uncached and len(items) <= 10:
        try:
            fresh = data_service.get_batch_quotes(uncached)
            if fresh:
                quotes.update(fresh)
        except Exception:
            pass

    # 计算总盈亏
    total_pnl = 0.0
    total_market = 0.0

    import time as _time
    html_parts = [f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font-size:12px;color:var(--text-secondary);"><span>更新: {_time.strftime("%H:%M:%S")}</span><span>排序: <a href="javascript:sortWatchlist(\'default\')" style="color:var(--accent)">默认</a> | <a href="javascript:sortWatchlist(\'change\')" style="color:var(--text-secondary)">涨跌幅</a> | <a href="javascript:sortWatchlist(\'name\')" style="color:var(--text-secondary)">名称</a></span></div><div class="watchlist-grid">']

    # 排序
    if sort == "change":
        items = sorted(items, key=lambda i: abs(quotes.get(i.stock_code, {}).get("change_pct", 0)), reverse=True)
    elif sort == "name":
        items = sorted(items, key=lambda i: i.stock_name)

    for item in items:
        q = quotes.get(item.stock_code)
        if q:
            price = q["price"]
            change_pct = q["change_pct"]
            color_class = "price-up" if change_pct >= 0 else "price-down"
            arrow = "↑" if change_pct >= 0 else "↓"
            price_str = f"{price:.2f}"
            change_str = f"{arrow}{abs(change_pct):.2f}%"

            # 计算盈亏
            pnl_str = ""
            if item.entry_price > 0 and item.shares > 0:
                pnl = (price - item.entry_price) * item.shares
                pnl_pct = (price - item.entry_price) / item.entry_price * 100
                total_pnl += pnl
                total_market += price * item.shares
                pnl_color = "price-up" if pnl >= 0 else "price-down"
                pnl_arrow = "+" if pnl >= 0 else ""
                pnl_str = f"<span class='card-pnl {pnl_color}'>{pnl_arrow}{pnl:.0f}元 ({pnl_arrow}{pnl_pct:.1f}%)</span>"
        else:
            price_str = "--"
            change_str = "--"
            color_class = ""

        has_position = item.entry_price > 0 and item.shares > 0

        # 买卖信号
        change_pct = q["change_pct"] if q else 0
        signal = ""
        if change_pct > 5: signal = '<span class="signal-dot hot" title="强势拉升"></span>'
        elif change_pct > 2: signal = '<span class="signal-dot up" title="温和上涨"></span>'
        elif change_pct > 0: signal = '<span class="signal-dot warm" title="微涨"></span>'
        elif change_pct > -2: signal = '<span class="signal-dot cool" title="微跌"></span>'
        elif change_pct > -5: signal = '<span class="signal-dot down" title="明显下跌"></span>'
        else: signal = '<span class="signal-dot cold" title="大跌"></span>'

        html_parts.append(
            f"<a href='/stock/{item.stock_code}' class='stock-card{' has-position' if has_position else ''}'>"
            f"<div class='card-header'>"
            f"<span class='card-name'>{signal} {item.stock_name}</span>"
            f"<span class='card-code'>{item.stock_code}</span>"
            f"</div>"
            f"<div class='card-body'>"
            f"<span class='card-price {color_class}'>{price_str}</span>"
            f"<span class='card-change {color_class}'>{change_str}</span>"
            f"</div>"
            f"{pnl_str}"
            f"<button class='btn-edit-pos' onclick=\"event.preventDefault();editPosition('{item.stock_code}','{item.stock_name}',{item.entry_price},{item.shares})\" title='编辑持仓'>"
            f"{'📝 持仓' if has_position else '+ 持仓'}</button>"
            f"</a>"
        )

    html_parts.append("</div>")

    # 总盈亏汇总
    if total_pnl != 0:
        pnl_color = "price-up" if total_pnl >= 0 else "price-down"
        pnl_arrow = "+" if total_pnl >= 0 else ""
        html_parts.append(
            f"<div class='pnl-card'><div class='pnl-header'>"
            f"<span>持仓汇总</span>"
            f"<span class='pnl-total {pnl_color}'>{pnl_arrow}{total_pnl:.0f}元</span>"
            f"<span class='pnl-pct {pnl_color}'>({pnl_arrow}{(total_pnl/total_market*100 if total_market else 0):.2f}%)</span>"
            f"<span style='color:var(--text-secondary);font-size:12px;margin-left:10px;'>市值 {total_market:.0f}元</span>"
            f"</div></div>"
        )

    html_parts.append("</div>")
    return HTMLResponse("".join(html_parts))


@router.get("/market")
async def get_market_data():
    """获取大盘数据 JSON。"""
    from app.services.data_service import data_service

    return {"indices": data_service.get_market_overview()}
