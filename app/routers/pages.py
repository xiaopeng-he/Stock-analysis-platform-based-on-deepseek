"""页面路由——首页、个股详情页。"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

templates_dir = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)), auto_reload=True)

router = APIRouter()


def _render(name: str, ctx: dict) -> HTMLResponse:
    template = _jinja_env.get_template(name)
    return HTMLResponse(template.render(**ctx))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _render("index.html", {"request": request})


@router.get("/news", response_class=HTMLResponse)
async def news_page(request: Request):
    return _render("news.html", {"request": request, "active_tab": "news"})


@router.get("/stock/{stock_code}", response_class=HTMLResponse)
async def stock_detail(request: Request, stock_code: str):
    """个股详情页——秒级响应，不阻塞等API。行情由SSE实时推送。"""
    return _render(
        "stock_detail.html",
        {"request": request, "stock_code": stock_code, "stock_name": stock_code},
    )
