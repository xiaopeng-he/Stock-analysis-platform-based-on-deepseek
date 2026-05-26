# A股智析 (A-Stock Advisor)

> 基于 DeepSeek API 的 A 股实时智能分析平台  
> 50 个 API 端点 · 12 类技术指标 · 7 维分析框架 · 6 因子选股模型

## 功能总览

### AI 投研
- **个股七维深度分析**：技术面/资金面/事件面/趋势/行为金融/风险量化/操作建议
- **一键诊股**：输入代码，秒出结论（推荐买入/关注/观望/回避）
- **自然语言问答**：像聊天一样问"宁德时代贵不贵？"
- **AI 输出调节**：看不懂→白话 / 更专业 / 只要重点，三个按钮随时切换
- **每只股票一句话总结**

### 智能组合
- **输入资金+风险偏好**，AI 自动构建完整投资方案
- **买什么、买多少、何时买、何时卖**——精确到股数
- **单股价上限**过滤，小资金只推买得起的股票
- **220+ 只参照股票池**（含 120 只低价股）
- 导出/复制方案

### 技术分析
- **K 线图叠加均线**：MA5/MA10/MA20/MA60
- **多周期切换**：1分/5分/15分/30分/60分/日K
- **12 类技术指标**：MACD/KDJ/RSI/布林带/OBV/CCI/WR/ATR/量价/支撑阻力/均线系统/综合趋势评分

### 选股工具
- **条件选股器**：价格/PE/涨跌幅/换手率 五维筛选 + 4 个快捷预设
- **自然语言选股**：说"帮我找高股息低负债的股票"就能筛选
- **六因子评分推荐**：动量/资金/板块/估值/催化剂/风控
- **股票对比**：最多 5 只同屏对比

### 持仓管理
- **盈亏实时跟踪**：成本价/现价/盈亏额/盈亏率
- **持仓诊断**：AI 分析质量 + 调仓建议（持有/加仓/减仓/清仓）
- **行业暴露分析**：行业集中度 + 风格分类（成长/价值/周期/防御）
- **行业轮动监测**

### 风险控制
- **VaR(95%)** / **最大回撤** / **年化波动率**
- **夏普比率** / **索提诺比率**
- **贝塔系数** / **相关性矩阵**
- **压力测试**：±5%/±10%/±20%/±30% 四情景
- **风险等级灯**：🟢🟡🔴

### 交易复盘
- **交易日志**：记录每笔交易的买入理由、卖出理由、情绪状态
- **错误类型识别**：追高/杀跌/仓位过重/频繁交易
- **胜率/盈亏比统计**
- **月度/季度/年度复盘报告**

### 资讯 & 学习
- **新闻聚合**：市场要闻 + 个股新闻，带原始链接
- **新手学堂**：AI 生成 5 大主题教学
- **18 个术语悬停解释**
- **每日市场简报**

### 报告
- **个股分析报告**（HTML 可打印版）
- **投资组合方案导出**（复制/下载 TXT）
- **分析历史自动保存**

## 技术栈

| 层面 | 技术 |
|------|------|
| Web 框架 | FastAPI + uvicorn |
| 实时推送 | Server-Sent Events (SSE) |
| 前端 | Jinja2 + HTMX + ECharts |
| 数据源 | 腾讯财经 / 新浪财经 / akshare（三源自动降级）|
| AI 引擎 | DeepSeek API (`deepseek-chat`, OpenAI 兼容) |
| 数据库 | SQLite + SQLAlchemy |
| 缓存 | 内存 dict + SQLite 双缓存 |

## 快速开始

### 环境要求
- Python 3.10+
- DeepSeek API Key（[platform.deepseek.com](https://platform.deepseek.com) 免费注册）

### 安装

```bash
git clone https://github.com/xiaopeng-he/Stock-analysis-platform-based-on-deepseek.git
cd Stock-analysis-platform-based-on-deepseek

# 安装依赖
pip install fastapi uvicorn openai akshare pandas sqlalchemy jinja2 requests sse-starlette python-dotenv
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek API Key
# DEEPSEEK_API_KEY=sk-xxxxxxxx
```

### 启动

```bash
python run.py
# 浏览器打开 http://localhost:8008
```

## 项目结构

```
├── run.py                          # 启动入口
├── .env.example                    # 配置模板
├── requirements.txt
├── app/
│   ├── main.py                     # FastAPI 应用 (50 routes)
│   ├── config.py                   # 配置管理
│   ├── routers/                    # 路由 (11个模块)
│   │   ├── pages.py                # 页面路由
│   │   ├── watchlist.py            # 自选股 CRUD
│   │   ├── stocks.py               # K线数据
│   │   ├── stream.py               # SSE 实时推送
│   │   ├── recommend.py            # 一键推荐
│   │   ├── portfolio.py            # 智能组合
│   │   ├── compare.py              # 多股对比
│   │   ├── market.py               # 市场数据 + 诊股
│   │   ├── history.py              # 历史记录 + 持仓诊断
│   │   ├── screener.py             # 条件选股
│   │   └── advanced.py             # 风险/日志/报告/简报
│   ├── services/                   # 核心服务 (9个模块)
│   │   ├── data_service.py         # 多源数据采集 (腾讯/新浪/akshare)
│   │   ├── ai_service.py           # DeepSeek AI 分析
│   │   ├── cache_service.py        # 双层缓存
│   │   ├── portfolio_service.py    # 投资组合引擎
│   │   ├── recommendation_service.py  # 推荐引擎
│   │   ├── technical_indicators.py # 12类技术指标计算
│   │   ├── risk_service.py         # 风险指标体系
│   │   ├── industry_service.py     # 行业分类 & 风格分析
│   │   ├── stock_reference.py      # 220+ 股票参照库
│   │   └── scheduler_service.py    # 定时调度
│   ├── models/                     # 数据模型 (4个)
│   ├── templates/                  # Jinja2 模板 (15+)
│   ├── static/                     # CSS/JS
│   └── utils/                      # Prompt / 限流器
├── data/                           # SQLite 数据库 (自动创建)
└── tests/
```

## API 端点 (50 个)

### 页面
| 路由 | 说明 |
|------|------|
| `GET /` | 首页 - 自选股 |
| `GET /stock/{code}` | 个股详情 |
| `GET /portfolio` | 智能投资组合 |
| `GET /screener` | 条件选股器 |
| `GET /recommend` | 一键推荐 |
| `GET /compare` | 股票对比 |
| `GET /news` | 市场资讯 |
| `GET /history` | 分析历史 |
| `GET /beginners` | 新手学堂 |
| `GET /report/{code}` | 个股可打印报告 |

### 行情 & 数据
| 路由 | 说明 |
|------|------|
| `GET /api/market` | 大盘指数 |
| `GET /api/market/snapshot` | 市场快照 |
| `GET /api/market/breadth` | 涨跌比统计 |
| `GET /api/news/market` | 市场要闻 |
| `GET /api/news/{code}` | 个股新闻 |
| `GET /api/stream?code=` | SSE 实时行情推送 |
| `GET /api/stock/{code}/kline?period=` | K线数据 (1/5/15/30/60/daily) |

### 选股 & 推荐
| 路由 | 说明 |
|------|------|
| `GET /api/screener/run` | 条件选股执行 |
| `GET /api/screener/nl?q=` | 自然语言选股 |
| `GET /api/recommend/stream` | AI推荐 SSE 流 |
| `GET /api/portfolio/build` | 构建投资组合 |
| `GET /api/quick-check?code=` | 一键诊股 |
| `GET /api/search?keyword=` | 股票搜索 |

### 分析 & 风险
| 路由 | 说明 |
|------|------|
| `GET /api/risk/{code}` | 个股综合风险报告 |
| `GET /api/risk/sortino/{code}` | 索提诺比率 |
| `GET /api/risk/portfolio-correlation` | 组合相关性矩阵 |
| `GET /api/portfolio/exposure` | 行业/风格暴露 |
| `GET /api/portfolio/audit` | 持仓诊断 |
| `GET /api/stock/{code}/oneliner` | 一句话总结 |
| `GET /api/adjust` | AI输出难度调节 |
| `GET /api/quickask?q=` | 自然语言问答 |
| `GET /api/compare/data` | 多股对比数据 |

### 交易 & 历史
| 路由 | 说明 |
|------|------|
| `POST /api/trade/log` | 记录交易 |
| `GET /api/trade/logs` | 交易日志列表 |
| `PUT /api/trade/{id}/review` | 复盘交易 |
| `GET /api/trade/summary` | 交易统计 |
| `GET /api/review/summary?period=` | 月度/季度/年度复盘 |
| `GET /api/history/list` | 分析历史 |

### 简报 & 教学
| 路由 | 说明 |
|------|------|
| `GET /api/briefing/daily` | 每日市场简报 |
| `GET /api/beginners/content?topic=` | AI 教学内容 |

## 注意事项

### 网络代理
如果系统配置了代理（如 VPN/Clash），可能拦截东方财富 API。代码已内置三数据源自动降级（腾讯→新浪→akshare），通常无需额外配置。

### 交易时段
A 股交易时间：周一至周五 9:30-11:30, 13:00-15:00（北京时间）。非交易时段自动降低数据采集频率。

### DeepSeek API 费用
DeepSeek API 定价极低（约 GPT-4 的 1/50），正常使用每月几元钱。

## 安全声明

- 本平台**不承诺收益**，所有分析仅供参考
- **不会自动下单**，不连接任何券商接口
- 明确区分"分析"和"投资建议"
- API Key 通过 `.env` 文件加密存储，**不会提交到 Git**
- 所有 AI 结论均标注置信度和数据来源

## License

MIT License - 详见 [LICENSE](LICENSE)

---

**免责声明：股市有风险，投资需谨慎。本平台的所有分析和推荐仅供学习参考，不构成投资建议。**
