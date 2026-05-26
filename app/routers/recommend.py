"""一键推荐 & 新手引导路由。"""

from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

templates_dir = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(templates_dir)), auto_reload=True)

router = APIRouter()


def _render(name: str, ctx: dict) -> HTMLResponse:
    template = _jinja_env.get_template(name)
    return HTMLResponse(template.render(**ctx))


# ── 一键推荐页面 ──
@router.get("/recommend", response_class=HTMLResponse)
async def recommend_page():
    """推荐页面——用户点击后触发 AI 分析。"""
    return _render("recommend.html", {})


# ── AI 推荐 API（SSE 流式推送分析进度）──
@router.get("/api/recommend/stream")
async def recommend_stream():
    """SSE 流式返回推荐结果——前端逐步展示。"""
    import asyncio
    import json
    from sse_starlette.sse import EventSourceResponse
    from app.services.recommendation_service import recommendation_service

    async def generate():
        # 先推送市场数据快照
        from app.services.data_service import data_service
        snapshot = data_service.get_all_market_data()
        yield {"event": "snapshot", "data": json.dumps({
            "indices": snapshot.get("indices", {}),
            "sectors": snapshot.get("sectors", [])[:8],
            "north_flow": snapshot.get("north_flow", {}),
            "limit_up_count": len(snapshot.get("limit_up", [])),
            "market_time": snapshot.get("market_time", ""),
        }, ensure_ascii=False)}

        # 等待 AI 分析（模拟进度）
        yield {"event": "status", "data": json.dumps({"msg": "正在采集全市场数据...", "progress": 20})}
        await asyncio.sleep(0.5)
        yield {"event": "status", "data": json.dumps({"msg": "DeepSeek AI 深度分析中...", "progress": 50})}

        # 获取 AI 推荐
        result = await recommendation_service.get_recommendations(force_refresh=True)
        yield {"event": "status", "data": json.dumps({"msg": "分析完成，生成推荐...", "progress": 90})}
        await asyncio.sleep(0.3)
        yield {"event": "result", "data": json.dumps(result, ensure_ascii=False)}
        yield {"event": "status", "data": json.dumps({"msg": "完成", "progress": 100})}

    return EventSourceResponse(generate())


# ── 新手引导页面 ──
@router.get("/beginners", response_class=HTMLResponse)
async def beginners_page():
    return _render("beginners.html", {})


# ── 新手教学内容 API ──
@router.get("/api/beginners/content")
async def get_beginner_content(topic: str = Query(default="basics")):
    from app.services.recommendation_service import recommendation_service
    result = await recommendation_service.get_beginner_content(topic)
    return result


# ── 市场快照 API ──
@router.get("/api/market/snapshot")
async def market_snapshot():
    from app.services.recommendation_service import recommendation_service
    return await recommendation_service.get_market_snapshot()


# ── 快速问答 API ──
@router.get("/api/quickask")
async def quick_ask(q: str = Query(default="")):
    if not q:
        return {"answer": "请输入你的问题"}
    from app.config import config
    if not config.DEEPSEEK_API_KEY:
        return {"answer": "请先配置 API Key"}
    try:
        from app.utils.prompt_builder import build_quick_question_prompt
        from app.services.data_service import data_service
        indices = data_service.get_market_overview()
        ctx = {
            "sh_index": f"{indices.get('上证指数', {}).get('price', 0):.2f}",
            "sz_index": f"{indices.get('深证成指', {}).get('price', 0):.2f}",
        }
        prompt = build_quick_question_prompt(q, ctx)

        from app.services.ai_service import ai_service
        response = ai_service.client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=500,
        )
        import json
        result = json.loads(response.choices[0].message.content.strip().strip("```json").strip("```").strip())
        return result
    except Exception as e:
        return {"answer": f"抱歉，当前无法回答：{str(e)[:80]}", "disclaimer": "AI回答仅供参考"}
