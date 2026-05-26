"""智能投资组合路由。"""

from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

templates_dir = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)), auto_reload=True)

router = APIRouter()


def _render(name: str, ctx: dict) -> HTMLResponse:
    return HTMLResponse(_jinja_env.get_template(name).render(**ctx))


@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page():
    return _render("portfolio.html", {"active_tab": "portfolio"})


@router.get("/api/portfolio/build")
async def build_portfolio(
    capital: float = Query(default=50000, ge=1000, le=10000000),
    risk: str = Query(default="稳健"),
    max_price: float = Query(default=0, ge=0, le=10000),
):
    """构建投资组合——GET /api/portfolio/build?capital=100000&risk=稳健&max_price=50"""
    from app.services.portfolio_service import portfolio_service
    result = await portfolio_service.build_portfolio(capital, risk, max_price)
    return result
