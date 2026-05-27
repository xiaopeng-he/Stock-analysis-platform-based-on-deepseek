"""
DeepSeek Prompt 构造器 —— 融入经济学理论、技术分析、行为金融学、风险管理等
专业分析框架。每个 Prompt 都是经过精心设计的分析模板。
"""

import json
from typing import Optional


def _format_indicators(tech: dict) -> str:
    """将技术指标字典格式化为 Prompt 可读文本。"""
    lines = []

    ma = tech.get("ma_system", {})
    ma_vals = ma.get("ma", {})
    if ma_vals:
        lines.append(f"  均线: {', '.join(f'{k}={v}' for k, v in sorted(ma_vals.items(), key=lambda x: int(x[0][2:])))}")
        lines.append(f"  均线排列: {ma.get('arrangement', 'N/A')}")
        cross = ma.get("cross_signal", "")
        if cross:
            lines.append(f"  交叉信号: {cross}")

    macd = tech.get("macd", {})
    if macd.get("dif_current") is not None:
        lines.append(f"  MACD: DIF={macd.get('dif_current',0):.4f} DEA={macd.get('dea_current',0):.4f} 柱={macd.get('macd_current',0):.4f} → {macd.get('signal','')}")

    kdj = tech.get("kdj", {})
    if kdj.get("k_current") is not None:
        lines.append(f"  KDJ: K={kdj.get('k_current',50)} D={kdj.get('d_current',50)} J={kdj.get('j_current',50)} → {kdj.get('signal','')}")

    rsi = tech.get("rsi", {})
    if rsi.get("rsi_current") is not None:
        lines.append(f"  RSI(14): {rsi.get('rsi_current',50)} → {rsi.get('signal','')}")

    bb = tech.get("bollinger", {})
    if bb.get("upper_current"):
        lines.append(f"  布林带: 上轨{bb.get('upper_current',0):.2f} 中轨{bb.get('middle_current',0):.2f} 下轨{bb.get('lower_current',0):.2f} 带宽{bb.get('bandwidth_pct',0)}% → {bb.get('signal','')}")

    vol = tech.get("volume", {})
    if vol.get("vol_ratio"):
        lines.append(f"  量价: 量比{vol.get('vol_ratio',1.0):.2f} (MA5/MA20) → {vol.get('signal','')}")

    atr = tech.get("atr", {})
    if atr.get("atr"):
        lines.append(f"  ATR: {atr.get('atr',0):.2f} ({atr.get('atr_pct',0)}%) → {atr.get('signal','')}")

    obv = tech.get("obv", {})
    if obv.get("signal"):
        lines.append(f"  OBV: {obv.get('signal','')} (趋势:{obv.get('obv_trend','')})")

    cci = tech.get("cci", {})
    if cci.get("cci_current") is not None:
        lines.append(f"  CCI(14): {cci.get('cci_current',0):.1f} → {cci.get('signal','')}")

    wr = tech.get("wr", {})
    if wr.get("wr_current") is not None:
        lines.append(f"  WR(14): {wr.get('wr_current',0):.1f} → {wr.get('signal','')}")

    sr = tech.get("sr_levels", {})
    if sr.get("nearest_support"):
        lines.append(f"  支撑/阻力: {sr.get('signal','')}")

    trend = tech.get("trend_summary", {})
    if trend:
        lines.append(f"  综合评分: {trend.get('strength',0)}/100 → {trend.get('overall','')}")

    return "\n".join(lines) if lines else "  技术指标暂不可用"


# ═══════════════════════════════════════════════
# 个股分析 Prompt（v2.0 专业版）
# ═══════════════════════════════════════════════
def build_analysis_prompt(
    stock_code: str, stock_name: str,
    quote: Optional[dict], klines: list[dict],
    news: list[dict],
    technical_indicators: Optional[dict] = None,
) -> str:
    """构建个股深度分析 Prompt——七维分析框架。"""

    # 行情
    if quote:
        quote_str = (
            f"最新价: {quote.get('price', 'N/A')}元  涨跌幅: {quote.get('change_pct', 'N/A')}%\n"
            f"今开: {quote.get('open', 'N/A')}  昨收: {quote.get('pre_close', 'N/A')}\n"
            f"最高: {quote.get('high', 'N/A')}  最低: {quote.get('low', 'N/A')}\n"
            f"成交量: {quote.get('volume', 'N/A')}手  成交额: {quote.get('amount', 'N/A')}元\n"
            f"换手率: {quote.get('turnover', 'N/A')}%  市盈率: {quote.get('pe', 'N/A')}"
        )
    else:
        quote_str = "实时行情数据暂不可用"

    # 新闻
    news_str = ""
    if news:
        for i, n in enumerate(news[:5], 1):
            news_str += f"  {i}. [{n.get('source', '')}] {n.get('title', '')}（{n.get('time', '')})\n"
    else:
        news_str = "暂无相关新闻"

    # 技术指标
    indicator_str = _format_indicators(technical_indicators) if technical_indicators else "未计算"

    # K线摘要（仅关键转折点）
    kline_str = ""
    if klines and len(klines) >= 10:
        for k in klines[-10:]:
            direction = "↑" if k['close'] > k['open'] else "↓"
            kline_str += f"  {k['time'][-8:]} {direction} O{k['open']:.2f} C{k['close']:.2f} H{k['high']:.2f} L{k['low']:.2f} V{k.get('volume',0):.0f}\n"

    return f"""# {stock_name}({stock_code}) 七维深度分析

你是一位拥有15年A股经验的**顶级量化分析师**，精通技术分析、行为金融学和A股独特的政策市博弈逻辑。请基于以下数据，进行严谨的多维度分析。

## 一、实时行情数据
{quote_str}

## 二、量化技术指标（已自动计算）
{indicator_str}

## 三、近期K线走势（最近10根）
{kline_str}

## 四、相关新闻事件
{news_str}

## 分析框架（七维度，缺一不可）

### 1. 技术面分析（权重30%）
- MACD/KDJ/RSI 的背离与共振
- 均线系统的排列与交叉信号
- 布林带位置与带宽暗示的变盘可能
- 量价关系的真实含义（放量/缩量+涨/跌的四种组合）
- 支撑位与压力位的判断

### 2. 资金面分析（权重20%）
- 换手率反映的市场活跃度
- 成交量变化趋势（5日均量 vs 20日均量）
- 量比分析——资金是进还是出

### 3. 新闻/事件面分析（权重15%）
- 新闻的真实性与影响力评估
- 利好/利空的程度分级
- 消息是否已被市场 price-in

### 4. 趋势判断（权重15%）
- 当前处于趋势的什么阶段（起涨/主升/盘顶/下跌/筑底）
- 趋势的持续性评估

### 5. 行为金融学分析（权重10%）
- 当前市场情绪判断（贪婪/恐惧/中性）
- 散户行为倾向（追涨杀跌还是观望）
- 是否存在羊群效应或过度反应

### 6. 风险量化评估（权重10%）
- ATR波动率 → 合理止损位
- 最大回撤预估
- 盈亏比判断

### 7. 综合操作建议
- 当前是否适合操作（观望/轻仓/正常/积极）
- 如果操作：开仓方向、仓位建议、止损位、目标位
- 不适合操作的话：等待什么信号

## 输出要求
严格按JSON格式输出（不要输出其他内容）：
{{
  "sentiment": "强烈看多|看多|中性偏多|中性|中性偏空|看空|强烈看空",
  "confidence": 0.0-1.0,
  "summary": "200字内综合分析摘要，涵盖七维度的核心结论",
  "key_points": ["关键点1", "关键点2", "关键点3", "关键点4", "关键点5"],
  "risk_warning": "具体风险提示与止损建议",
  "technical_analysis": "技术面七维分析（200字以内）",
  "news_impact": "新闻面影响评估",
  "operation_advice": {{
    "action": "观望|轻仓参与|正常操作|积极做多",
    "position_ratio": "建议仓位比例（如1/3仓）",
    "entry_zone": "合理开仓区间",
    "stop_loss": "止损位",
    "target_1": "第一目标位",
    "target_2": "第二目标位（可选）",
    "wait_signal": "如果不操作，等待什么信号"
  }},
  "behavioral_note": "行为金融学角度的特别提示"
}}"""


# ═══════════════════════════════════════════════
# 一键推荐 Prompt（v2.0 专业版——多因子选股框架）
# ═══════════════════════════════════════════════
def build_recommendation_prompt(market_data: dict) -> str:
    """构建多因子选股推荐 Prompt——融合宏观、中观、微观三层分析。"""

    # 大盘
    indices_str = ""
    for name, idx in market_data.get("indices", {}).items():
        arrow = "↑" if idx["change_pct"] >= 0 else "↓"
        indices_str += f"{name}: {idx['price']:.2f} {arrow}{abs(idx['change_pct']):.2f}%\n"

    # 强势板块
    sectors_str = ""
    for s in market_data.get("sectors", [])[:8]:
        sectors_str += f"{s['name']}: {s['change_pct']:+.2f}%  领涨: {s['leader']}\n"

    # 热门概念
    concepts_str = ""
    for c in market_data.get("concepts", [])[:8]:
        concepts_str += f"{c['name']}: {c['change_pct']:+.2f}%\n"

    # 涨幅榜 TOP 20
    gainers_str = ""
    for g in market_data.get("top_gainers", [])[:20]:
        gainers_str += f"{g['name']}({g['code']}) 价{g['price']:.2f} 涨幅{g['change_pct']:+.2f}% 换手{g.get('turnover',0):.1f}% PE{g.get('pe',0):.1f}\n"

    # 涨停板分析
    limit_up_str = ""
    for z in market_data.get("limit_up", [])[:15]:
        reason = f"（原因: {z.get('reason', '')})" if z.get('reason') else ""
        limit_up_str += f"{z['name']}({z['code']}) 连板{z.get('limit_times',1):.0f} {reason}\n"

    # 资金面
    nf = market_data.get("north_flow", {})
    north_str = f"今日北向资金净流入: {nf.get('today', 0):.2f}亿元"

    # 新闻
    news_str = ""
    for i, n in enumerate(market_data.get("market_news", [])[:8], 1):
        news_str += f"  {i}. {n.get('title', '')}\n"

    return f"""# A股全市场智能选股——多层分析框架

你是一位管理百亿规模的**顶级量化基金经理**，擅长自上而下（宏观→行业→个股）的多因子选股框架。请基于以下全市场数据，运用专业选股方法论，给出最佳投资组合建议。

## 第一步：宏观环境判断（宏观层）
**大盘指数**
{indices_str}

**资金面**
{north_str}

## 第二步：行业轮动分析（中观层）
**强势行业板块（涨幅前8）**
{sectors_str}

**热门概念板块（涨幅前8）**
{concepts_str}

## 第三步：个股精选（微观层）
**涨幅榜TOP20**
{gainers_str}

**涨停板精选**
{limit_up_str}

## 第四步：事件驱动
**市场要闻**
{news_str}

## 选股方法论（必须严格遵循）

### A. 多因子评分体系（每只候选股票按以下6因子打分，1-10分）

1. **动量因子**：近期涨幅排名、连板数 → 趋势强度
2. **资金因子**：换手率、成交额、北向资金流向 → 资金认可度
3. **板块因子**：是否属于今日最强板块/概念 → 板块效应
4. **估值因子**：PE是否在合理范围 → 安全边际
5. **事件因子**：是否有新闻/政策/业绩利好催化 → 催化剂强度
6. **风险因子**：波动率、回撤 → 风险可控度（分数越低越好→这里反向打分）

### B. 排除规则
- 已涨停封板的股票（无买入机会）
- PE > 500 或 PE < 0（亏损严重的纯炒作标的）
- 换手率 > 20%（过度投机，风险极高）
- ST、*ST股票

### C. 投资组合构建
- 推荐 5-8 只股票
- 必须包含：2-3只稳健型（大市值蓝筹）+ 3-5只进取型（中小市值成长）
- 板块分散，避免过度集中于同一行业
- 至少1只适合新手的低风险标的

## 输出要求
严格按JSON格式输出：
{{
  "market_assessment": "宏观环境研判（150字以内）——包含经济周期阶段判断、政策环境评估、市场情绪综合判断",
  "macro_analysis": {{
    "cycle_stage": "当前经济周期阶段判断",
    "policy_direction": "政策环境判断",
    "market_sentiment": "市场整体情绪（贪婪/中性/恐惧）",
    "index_trend": "大盘趋势方向"
  }},
  "sector_rotation": {{
    "leading_sectors": ["当前领涨板块1", "板块2"],
    "rotation_direction": "板块轮动方向描述",
    "sector_advice": "板块配置建议"
  }},
  "hot_direction": "今日市场主线方向（50字）",
  "risk_level": "低|中|高",
  "recommendations": [
    {{
      "code": "股票代码",
      "name": "股票名称",
      "current_price": 0.00,
      "factor_scores": {{
        "momentum": 7,
        "capital_flow": 8,
        "sector": 8,
        "valuation": 6,
        "catalyst": 7,
        "risk_control": 7
      }},
      "total_score": 43,
      "reason": "基于多因子评分的推荐理由（100字以内）",
      "strategy": "具体操作策略（60字以内）",
      "target_pct": 5.0,
      "stop_loss_pct": -3.0,
      "hold_days": "3-5日",
      "risk_level": "低|中|高",
      "suitable_for": "新手|有经验|均可",
      "entry_timing": "最佳入场时机判断"
    }}
  ],
  "risk_warnings": ["全局风险1", "风险2", "风险3", "风险4"],
  "beginner_advice": "给新手投资者的特别建议（120字以内）——包括仓位管理建议、心态建议",
  "market_outlook": "未来1-3个交易日市场展望（80字以内）"
}}"""


# ═══════════════════════════════════════════════
# 新手教学 Prompt（保持不变）
# ═══════════════════════════════════════════════
# ═══════════════════════════════════════════════
# 智能投资组合配置 Prompt（v0.5 核心功能）
# ═══════════════════════════════════════════════
def build_portfolio_prompt(market_data: dict, capital: float, risk_profile: str, max_price: float = 0) -> str:
    """构建智能资产配置 Prompt——基于底仓金额、风险偏好和单股价上限。"""

    indices_str = ""
    for name, idx in market_data.get("indices", {}).items():
        arrow = "↑" if idx["change_pct"] >= 0 else "↓"
        indices_str += f"{name}: {idx['price']:.2f} {arrow}{abs(idx['change_pct']):.2f}%\n"

    sectors_str = ""
    for s in market_data.get("sectors", [])[:8]:
        sectors_str += f"  {s['name']}: {s['change_pct']:+.2f}%  领涨:{s.get('leader','')}\n"

    gainers_str = ""
    for g in market_data.get("top_gainers", [])[:25]:
        gainers_str += f"  {g['name']}({g['code']}) {g['price']:.2f}元 涨{g['change_pct']:+.2f}% 换手{g.get('turnover',0):.1f}% PE{g.get('pe',0):.1f}\n"

    nf = market_data.get("north_flow", {})
    north_str = f"北向资金今日净流入: {nf.get('today', 0):.2f}亿元"

    news_str = ""
    for i, n in enumerate(market_data.get("market_news", [])[:5], 1):
        news_str += f"  {i}. {n.get('title', '')}\n"

    # 计算每只候选股的最小购买成本（1手=100股）
    candidates_with_cost = []
    for g in market_data.get("top_gainers", [])[:30]:
        price = g.get("price", 0)
        lot_cost = price * 100  # 1手=100股
        if lot_cost <= 0:
            continue
        # 如果用户设置了单股价上限，直接过滤
        if max_price > 0 and price > max_price:
            continue
        affordable = lot_cost <= capital * 0.25  # 单只不超过25%总资金
        candidates_with_cost.append({
            **g,
            "lot_cost": lot_cost,
            "affordable": affordable,
        })

    if candidates_with_cost:
        gainers_str = ""
        for g in candidates_with_cost:
            affordable_mark = "✓" if g["affordable"] else "✗"
            gainers_str += f"  {g['name']}({g['code']}) 价{g['price']:.2f}元 1手={g['lot_cost']:.0f}元 涨{g['change_pct']:+.2f}% 换手{g.get('turnover',0):.1f}% PE{g.get('pe',0):.1f} {affordable_mark}\n"
    else:
        gainers_str = "暂无数据"

    # 风险配置策略
    risk_strategies = {
        "保守": "以低价蓝筹和低估值防御型股票为主(70%)。单只股票必须是你买得起的——1手价格≤总资金的20%。保留至少20%现金。最大回撤控制在5%以内。",
        "稳健": "低价蓝筹(40%)+中小盘成长(40%)+热点(20%)。单只股票必须买得起。保留10-15%现金。最大回撤控制在10%以内。",
        "进取": "中小盘成长(45%)+热点题材(30%)+低价蓝筹(25%)。单只股票必须买得起。可满仓但必须设止损。可承受15%回撤。",
    }
    strategy = risk_strategies.get(risk_profile, risk_strategies["稳健"])

    # 资金量级提示
    max_price_constraint = f"**单股价上限: ≤{max_price:.0f}元/股**，即1手≤{max_price*100:.0f}元。" if max_price > 0 else ""
    if capital <= 2000:
        capital_note = (f"⚠️ 资金仅{capital:.0f}元，属于极小资金。{max_price_constraint}"
                        f"**只能买1-2只股票**，建议全仓1只最看好的低价股。A股1手=100股，最多买得起{capital/100:.0f}元/股的股票。"
                        f"不要试图分散——集中火力才能让小资金成长。严格止损-5%。")
    elif capital <= 5000:
        capital_note = f"资金{capital:.0f}元，小资金。{max_price_constraint}精选1-2只即可，不要过度分散。"
    elif capital <= 20000:
        capital_note = f"资金{capital:.0f}元。{max_price_constraint}精选2-3只股。"
    elif capital <= 100000:
        capital_note = f"资金{capital//10000}万元。{max_price_constraint}可配置3-5只股。"
    else:
        capital_note = f"资金{capital//10000}万元。{max_price_constraint}可配置4-6只股。"

    return f"""# 智能投资组合构建任务

你是一位管理百亿资产的**首席投资官(CIO)**，精通现代投资组合理论、风险预算和A股实战。请为一位个人投资者构建完整的投资组合方案。

## 投资者画像
- 可用资金: **{capital:.0f}元**
- 风险偏好: **{risk_profile}型**
- 投资目标: 在控制风险的前提下获取合理收益
- 投资期限: 短期波段(3-10个交易日)

## 当前市场环境
**大盘指数:**
{indices_str}
**资金面:** {north_str}
**强势板块:**
{sectors_str}

## 候选标的池
**今日强势股(涨幅榜):**
{gainers_str}

## 市场要闻
{news_str}

## 配置策略约束
{strategy}

## 仓位管理铁律（必须遵守——按优先级排序）

**规则0：买得起才是硬道理（最高优先级）**
- 每只股票需要以"手"(100股)为单位买入
- 1手成本 = 股价 × 100。例如股价10元→1手=1000元
- **你推荐的每只股票的1手成本必须 ≤ 该股票分配到的资金额**
- 标记为✗的股票绝对不要推荐——买不起
- 如果资金太少导致可选股很少，就少推荐几只（2-3只即可），质量比数量重要

**规则1：单只股票不超过总资金25%**
**规则2：总仓位不超过{85 if risk_profile == '保守' else 100 if risk_profile == '进取' else 90}%**
**规则3：每只股票必须设硬止损(-3%~-5%)**
**规则4：止盈分批——目标1减半仓，目标2清仓**
**规则5：不追涨停、不买ST、不买PE>500或亏损股、不买换手>20%的投机股**
**规则6：{capital_note}**
**规则7：所有金额必须精确到元，股数必须是100的整数倍**

## 输出要求
严格按JSON格式输出（不要输出其他内容）：
{{
  "market_judgment": "当前市场环境综合判断(80字)——是否适合入场、整体风险水平",
  "allocation": {{
    "total_capital": {capital:.0f},
    "cash_reserve": 0,
    "cash_reserve_pct": 0,
    "invested_amount": 0,
    "expected_return": "预期收益区间(如+3%~+8%)",
    "max_drawdown_estimate": "最大回撤预估"
  }},
  "positions": [
    {{
      "code": "股票代码",
      "name": "股票名称",
      "type": "蓝筹防守|成长白马|热点题材",
      "current_price": 0.00,
      "allocation_pct": 15.0,
      "allocation_amount": 15000.0,
      "suggested_shares": 0,
      "entry_zone": "合理买入价格区间",
      "stop_loss": 0.00,
      "stop_loss_pct": -3.0,
      "target_1": 0.00,
      "target_1_pct": 5.0,
      "target_2": 0.00,
      "target_2_pct": 10.0,
      "hold_days": "建议持仓天数",
      "risk_level": "低|中|高",
      "reason": "选股逻辑——为什么选这只(80字)",
      "operation": "具体操作指引(买入时机、仓位管理)"
    }}
  ],
  "risk_controls": {{
    "portfolio_stop_loss": "组合整体止损线",
    "portfolio_take_profit": "组合止盈策略",
    "daily_max_loss": "单日最大亏损容忍度",
    "rebalance_rule": "何时调整持仓"
  }},
  "beginner_guide": "给新手的一句话操作总结(50字)——傻瓜式、可照做",
  "disclaimer": "风险免责声明(20字)"
}}

## 特别要求
- 推荐 **4-7 只**股票，精确到买卖多少股
- 必须包含至少 2 只**低风险蓝筹**做压舱石
- {risk_profile}型特别适合的股票类型要占主导
- 每笔交易的具体操作步骤要明确到"傻瓜都能执行"
- 资金分配精确到元，股票数量精确到100股(1手)的整数倍
- 给出组合整体的预期收益和风险敞口"""
    topics = {
        "basics": "A股基本知识（什么是A股、交易所、交易时间、T+1制度、涨跌停限制、交易费用、股票代码含义）",
        "analysis": "如何分析一只股票（基本面分析、技术面分析、新闻面分析、资金面分析的基础入门）",
        "strategy": "新手适用的交易策略（价值投资、趋势跟踪、定投策略、如何设置止盈止损）",
        "risk": "炒股风险管理和心态建设（仓位管理、分散投资、避免追涨杀跌、如何控制情绪）",
        "terms": "A股常见术语大全（换手率、量比、PE市盈率、PB市净率、总市值、流通市值、涨停板、龙虎榜、北向资金、MACD、KDJ、RSI、布林带、均线等20个核心术语的通俗解释）",
    }
    topic_desc = topics.get(topic, topics["basics"])
    return f"""你是一位资深的A股投资者教育专家，擅长用通俗易懂的语言向新手讲解炒股知识。

请围绕以下主题，为A股初学者写一篇通俗易懂的教学内容：

## 教学主题
{topic_desc}

## 要求
1. 用白话解释，避免过于专业的金融术语。如果必须用术语，一定要用括号解释
2. 多用生活中的比喻来解释股票概念
3. 给出具体的例子（用真实的股票代码和场景）
4. 控制在 500-800 字
5. 结尾给一句鼓励的话
6. 内容要有温度，像一个有经验的朋友在分享心得

请严格按以下 JSON 格式输出：
{{
  "title": "给文章起一个吸引人的标题",
  "content": "文章正文（支持简单的 Markdown 格式，用 \\n 换行）",
  "key_takeaway": "一句话总结核心要点",
  "next_topic": "建议下一步学习什么"
}}"""


# ═══════════════════════════════════════════════
# 快速问答 Prompt
# ═══════════════════════════════════════════════
def build_quick_question_prompt(question: str, context: dict) -> str:
    return f"""你是一位专业的A股投资顾问。一位投资者向你提问：

问题：{question}

当前市场背景：
- 上证指数：{context.get('sh_index', 'N/A')}
- 深证成指：{context.get('sz_index', 'N/A')}

请用通俗易懂的方式回答，注意：
1. 直接回答问题，不要绕弯子
2. 如果有风险，一定要明确提示
3. 回答控制在200字以内
4. 用生活化的语言，别太学术

请严格按以下 JSON 格式输出：
{{
  "answer": "你的回答",
  "disclaimer": "免责声明（15字以内）"
}}"""
