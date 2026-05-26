# CLAUDE.md

## 项目概述

A股智析 — 基于 DeepSeek API 的 A 股实时智能分析平台。

## 运行环境

- **Conda 环境**: `daily_stock_analysis`
- **运行方式**: `conda run -n daily_stock_analysis uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **开发模式**: `conda run -n daily_stock_analysis uvicorn app.main:app --reload`

## 安全规则

1. **API Key 管理**: DeepSeek API Key 通过 `.env` 文件管理，禁止写入源码或提交到 Git
2. **禁止批量删除**：禁止执行 `rm -rf`、`rm -r`、`rm *`、`del /s`、`find . -delete`、`git clean -fd` 等命令
3. **禁止未经授权操作**：Git commit/push/reset/rebase、修改环境变量、安装/卸载/升级依赖等需用户确认
4. **依赖安装**：新增依赖前说明名称、用途、必要性、替代方案，经用户同意后方可安装
5. **代码修改原则**：先读后改、小步提交、不擅自重构、不删除用户代码

## 项目结构

```
astock-advisor/
├── app/
│   ├── main.py            # FastAPI 应用入口
│   ├── config.py          # 配置管理
│   ├── routers/           # 路由 (pages, stocks, watchlist, stream)
│   ├── services/          # 服务 (data, ai, cache, scheduler)
│   ├── models/            # 数据模型 (database, watchlist, analysis_log)
│   ├── templates/         # Jinja2 模板
│   ├── static/            # 静态资源 (CSS, JS)
│   └── utils/             # 工具 (prompt_builder, rate_limiter)
├── data/                  # SQLite 数据库
├── tests/                 # 测试
└── .env.example           # 环境变量模板
```

## 技术栈

- **Web**: FastAPI + Jinja2 + SSE
- **前端**: HTMX + ECharts (CDN)
- **数据**: akshare (东方财富), SQLite
- **AI**: DeepSeek API (OpenAI 兼容)
- **缓存**: 内存 dict + SQLite
