"""FastAPI 应用入口——创建 app、注册路由、配置中间件和生命周期事件。"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import config


@asynccontextmanager
async def lifespan(application: FastAPI):
    """应用生命周期管理：启动时初始化数据库 + 预热缓存。"""
    from app.models.database import init_db
    init_db()

    # 后台预热缓存——首个请求不再等待
    asyncio.create_task(_warmup_cache())

    yield
    pass


async def _warmup_cache():
    """后台预热：提前加载大盘指数和热门股票行情。"""
    try:
        from app.services.data_service import data_service
        # 预热大盘指数
        data_service.get_market_overview()
        # 预热热门股票行情（演示自选股）
        data_service.get_batch_quotes(["600519", "000001", "300750", "000858", "601318", "002594"])
        # 预热日K线
        data_service.get_daily_kline("000001")
        print("[Warmup] Cache pre-loaded successfully")
    except Exception as e:
        print(f"[Warmup] Partial failure (non-critical): {e}")


app = FastAPI(
    title="A股智析",
    description="基于 DeepSeek API 的 A 股实时智能分析平台",
    version="0.4.0",
    lifespan=lifespan,
)

# ── 全局响应头（禁用不必要的浏览器缓存，但允许 CDN 缓存静态资源）──
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class CacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        elif path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache"
        return response


app.add_middleware(CacheMiddleware)

# ── 静态文件 ──
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ── 注册路由（延迟导入避免循环依赖） ──
def register_routers():
    from app.routers import pages, stocks, watchlist, stream, recommend, compare, portfolio, market, history, screener, advanced

    app.include_router(pages.router)
    app.include_router(stocks.router, prefix="/api")
    app.include_router(watchlist.router, prefix="/api")
    app.include_router(stream.router, prefix="/api")
    app.include_router(recommend.router)
    app.include_router(compare.router)
    app.include_router(portfolio.router)
    app.include_router(market.router)
    app.include_router(history.router)
    app.include_router(screener.router)
    app.include_router(advanced.router)


register_routers()


# ── 直接运行入口 ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=True)
