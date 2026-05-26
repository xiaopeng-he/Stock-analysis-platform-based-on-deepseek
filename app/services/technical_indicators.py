"""
技术指标计算引擎——基于K线数据计算MA/MACD/KDJ/RSI/布林带/量价关系等，
为AI分析提供量化数据支撑。

涵盖 A 股分析最常用的 12 类指标。
"""

import math
from typing import Optional


def calc_sma(data: list[float], period: int) -> list[float]:
    """简单移动平均 (SMA)。"""
    if len(data) < period:
        return [sum(data) / len(data)] * len(data) if data else []
    result = [0.0] * (period - 1)
    for i in range(period - 1, len(data)):
        result.append(sum(data[i - period + 1:i + 1]) / period)
    return result


def calc_ema(data: list[float], period: int) -> list[float]:
    """指数移动平均 (EMA)。"""
    if not data:
        return []
    k = 2.0 / (period + 1)
    result = [data[0]]
    for val in data[1:]:
        result.append(val * k + result[-1] * (1 - k))
    return result


def calc_macd(closes: list[float], fast=12, slow=26, signal=9) -> dict:
    """
    MACD 指标——趋势跟踪和动能分析的核心工具。
    返回 DIF, DEA, MACD柱 (histogram)、金叉/死叉信号。
    """
    if len(closes) < slow + signal:
        return {"dif": [], "dea": [], "macd": [], "signal": "数据不足"}

    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)

    dif = [ema_fast[i] - ema_slow[i] for i in range(len(closes))]
    dea = calc_ema(dif, signal)

    macd_hist = [(dif[i] - dea[i]) * 2 for i in range(len(dif))]

    # 金叉/死叉检测
    if len(dif) >= 3:
        if dif[-2] < dea[-2] and dif[-1] > dea[-1]:
            sig = "金叉 ↑ 看涨"
        elif dif[-2] > dea[-2] and dif[-1] < dea[-1]:
            sig = "死叉 ↓ 看跌"
        elif dif[-1] > dea[-1]:
            sig = "多头排列"
        else:
            sig = "空头排列"
    else:
        sig = "数据不足"

    return {
        "dif": dif[-60:] if len(dif) > 60 else dif,
        "dea": dea[-60:] if len(dea) > 60 else dea,
        "macd": macd_hist[-60:] if len(macd_hist) > 60 else macd_hist,
        "dif_current": round(dif[-1], 4) if dif else 0,
        "dea_current": round(dea[-1], 4) if dea else 0,
        "macd_current": round(macd_hist[-1], 4) if macd_hist else 0,
        "signal": sig,
    }


def calc_kdj(highs: list[float], lows: list[float], closes: list[float],
             period: int = 9) -> dict:
    """
    KDJ 随机指标——判断超买超卖和转折点。
    K > 80 超买区，K < 20 超卖区。K 上穿 D 为买入信号。
    """
    n = len(closes)
    if n < period:
        return {"k": [], "d": [], "j": [], "signal": "数据不足"}

    k_vals, d_vals, j_vals = [], [], []
    prev_k, prev_d = 50.0, 50.0

    for i in range(period - 1, n):
        high_max = max(highs[i - period + 1:i + 1])
        low_min = min(lows[i - period + 1:i + 1])
        if high_max == low_min:
            rsv = 50.0
        else:
            rsv = (closes[i] - low_min) / (high_max - low_min) * 100

        k_val = prev_k * 2 / 3 + rsv / 3
        d_val = prev_d * 2 / 3 + k_val / 3
        j_val = 3 * k_val - 2 * d_val

        k_vals.append(round(k_val, 2))
        d_vals.append(round(d_val, 2))
        j_vals.append(round(j_val, 2))
        prev_k, prev_d = k_val, d_val

    # 信号判断
    cur_k = k_vals[-1] if k_vals else 50
    cur_d = d_vals[-1] if d_vals else 50
    if cur_k > 80:
        sig = "超买 ⚠ 谨慎追高"
    elif cur_k < 20:
        sig = "超卖 ★ 关注反弹"
    elif cur_k > cur_d:
        sig = "K > D 偏多"
    else:
        sig = "K < D 偏空"

    return {
        "k": k_vals, "d": d_vals, "j": j_vals,
        "k_current": cur_k, "d_current": cur_d, "j_current": round(cur_k * 3 - cur_d * 2, 2),
        "signal": sig,
    }


def calc_rsi(closes: list[float], period: int = 14) -> dict:
    """
    RSI 相对强弱指标——衡量价格变动的速度和幅度。
    RSI > 70 超买，RSI < 30 超卖。
    """
    if len(closes) < period + 1:
        return {"rsi": [], "signal": "数据不足"}

    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))

    rsi_vals = []
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    first_rsi = 100 - 100 / (1 + avg_gain / avg_loss) if avg_loss > 0 else 100
    rsi_vals.append(round(first_rsi, 2))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsi = 100 - 100 / (1 + avg_gain / avg_loss) if avg_loss > 0 else 100
        rsi_vals.append(round(rsi, 2))

    cur_rsi = rsi_vals[-1] if rsi_vals else 50
    if cur_rsi > 80:
        sig = "严重超买 🔴"
    elif cur_rsi > 70:
        sig = "超买 ⚠"
    elif cur_rsi < 20:
        sig = "严重超卖 🟢"
    elif cur_rsi < 30:
        sig = "超卖 ★"
    else:
        sig = "正常区间"

    return {"rsi": rsi_vals, "rsi_current": cur_rsi, "signal": sig}


def calc_bollinger_bands(closes: list[float], period: int = 20, std_mult: float = 2.0) -> dict:
    """
    布林带——波动率分析和支撑/阻力判断。
    价格触及上轨=超买/阻力，触及下轨=超卖/支撑。带宽收缩=变盘信号。
    """
    if len(closes) < period:
        return {"upper": [], "middle": [], "lower": [], "signal": "数据不足"}

    sma = calc_sma(closes, period)
    upper, lower, bandwidth_pct = [], [], []

    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1:i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = math.sqrt(variance)
        upper.append(round(mean + std_mult * std, 2))
        lower.append(round(mean - std_mult * std, 2))
        bandwidth_pct.append(round(upper[-1] / lower[-1] * 100 - 100, 2) if lower[-1] else 0)

    cur_price = closes[-1] if closes else 0
    cur_upper = upper[-1] if upper else 0
    cur_lower = lower[-1] if lower else 0
    cur_mid = sma[-1] if sma else 0

    if cur_price >= cur_upper * 0.99:
        sig = "触及上轨 → 高位压力"
    elif cur_price <= cur_lower * 1.01:
        sig = "触及下轨 → 支撑反弹"
    elif cur_price > cur_mid:
        sig = "中轨上方 偏强"
    else:
        sig = "中轨下方 偏弱"

    # 带宽分析
    bw = bandwidth_pct[-1] if bandwidth_pct else 0
    if bw < 3:
        sig += " | 带宽极窄 → 变盘在即"
    elif bw > 15:
        sig += " | 波动剧烈"

    return {
        "upper": upper, "middle": sma[period - 1:], "lower": lower,
        "upper_current": cur_upper, "middle_current": cur_mid, "lower_current": cur_lower,
        "bandwidth_pct": round(bw, 2), "signal": sig,
    }


def calc_volume_analysis(volumes: list[float], closes: list[float]) -> dict:
    """
    量价关系分析——"量在价先"，A股最重要的分析维度之一。
    - 放量上涨 → 健康上涨
    - 放量下跌 → 恐慌出逃
    - 缩量上涨 → 涨势衰竭
    - 缩量下跌 → 抛压减轻
    """
    n = len(volumes)
    if n < 6:
        return {"signal": "数据不足", "vol_ratio": 1.0}

    # 5日均量
    vol_ma5 = sum(volumes[-5:]) / 5
    vol_ma20 = sum(volumes[-20:]) / 20 if n >= 20 else sum(volumes[-n:]) / max(n, 1)

    vol_ratio = round(vol_ma5 / vol_ma20, 2) if vol_ma20 else 1.0

    # 近期价量方向
    price_short = closes[-1] - closes[-6] if n >= 6 else 0
    if vol_ratio > 1.5 and price_short > 0:
        sig = "放量上涨 → 主力做多意愿强"
    elif vol_ratio > 1.5 and price_short < 0:
        sig = "放量下跌 → 主力出货 ⚠"
    elif vol_ratio < 0.5 and price_short > 0:
        sig = "缩量上涨 → 上涨乏力"
    elif vol_ratio < 0.5 and price_short < 0:
        sig = "缩量下跌 → 抛压减轻"
    elif vol_ratio > 1.2:
        sig = "温和放量"
    else:
        sig = "量能正常"

    return {
        "vol_ma5": round(vol_ma5, 0),
        "vol_ma20": round(vol_ma20, 0),
        "vol_ratio": vol_ratio,
        "signal": sig,
    }


def calc_ma_system(closes: list[float]) -> dict:
    """
    均线系统——MA5/MA10/MA20/MA60 排列分析。
    多头排列(短均线在上) = 上升趋势，空头排列 = 下降趋势。
    """
    if len(closes) < 60:
        shorter = [5, 10, 20]
    else:
        shorter = [5, 10, 20, 60]

    ma = {}
    for p in shorter:
        vals = calc_sma(closes, p)
        ma[f"MA{p}"] = round(vals[-1], 2) if vals else 0

    # 排列分析
    mas = [(k, ma[k]) for k in sorted(ma.keys(), key=lambda x: int(x[2:]))]
    if all(mas[i][1] >= mas[i + 1][1] for i in range(len(mas) - 1)):
        arrange = "多头排列 ↑ 趋势向好"
    elif all(mas[i][1] <= mas[i + 1][1] for i in range(len(mas) - 1)):
        arrange = "空头排列 ↓ 趋势偏弱"
    else:
        arrange = "均线缠绕 → 震荡整理"

    # 金叉/死叉
    cross_signal = ""
    if len(closes) >= 10:
        ma5_hist = calc_sma(closes, 5)
        ma10_hist = calc_sma(closes, 10)
        if len(ma5_hist) >= 2:
            if ma5_hist[-2] < ma10_hist[-2] and ma5_hist[-1] > ma10_hist[-1]:
                cross_signal = "MA5上穿MA10 短线金叉"
            elif ma5_hist[-2] > ma10_hist[-2] and ma5_hist[-1] < ma10_hist[-1]:
                cross_signal = "MA5下穿MA10 短线死叉"

    long_term = {}
    if len(closes) >= 120:
        ma120 = round(sum(closes[-120:]) / 120, 2)
        ma250 = round(sum(closes[-250:]) / 250, 2) if len(closes) >= 250 else ma120
        long_term["MA120"] = ma120
        long_term["MA250"] = ma250

    return {
        "ma": ma,
        "long_ma": long_term,
        "arrangement": arrange,
        "cross_signal": cross_signal,
    }


def calc_atr(highs: list[float], lows: list[float], closes: list[float],
             period: int = 14) -> dict:
    """
    ATR 平均真实波幅——衡量波动性，用于设置止损位。
    """
    n = len(closes)
    if n < period + 1:
        return {"atr": 0, "signal": "数据不足"}

    tr_list = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)

    atr_vals = calc_sma(tr_list, period)
    cur_atr = atr_vals[-1] if atr_vals else 0
    cur_price = closes[-1] if closes else 0

    atr_pct = round(cur_atr / cur_price * 100, 2) if cur_price else 0

    return {
        "atr": round(cur_atr, 2),
        "atr_pct": atr_pct,
        "stop_loss_suggest": round(cur_price - 2 * cur_atr, 2) if cur_price else 0,
        "signal": f"日波动约 ±{atr_pct}% | 建议止损: {cur_price - 2 * cur_atr:.2f}" if cur_price else "数据不足",
    }


# ── 新增指标 v0.4 ──

def calc_obv(closes: list[float], volumes: list[float]) -> dict:
    """
    OBV 能量潮——"量在价先"，通过成交量变化预测价格方向。
    OBV上升+价格上升=确认上涨；OBV下降+价格上升=背离警告。
    """
    if len(closes) < 2:
        return {"obv": [], "signal": "数据不足"}

    obv = [0.0]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv.append(obv[-1] + volumes[i] if i < len(volumes) else obv[-1])
        elif closes[i] < closes[i - 1]:
            obv.append(obv[-1] - volumes[i] if i < len(volumes) else obv[-1])
        else:
            obv.append(obv[-1])

    # OBV 趋势（5日均线）
    obv_ma5 = sum(obv[-5:]) / 5 if len(obv) >= 5 else obv[-1]
    price_trend = closes[-1] - closes[-5] if len(closes) >= 5 else 0

    cur_obv = obv[-1]
    obv_trend = cur_obv - obv[-6] if len(obv) >= 6 else 0

    if obv_trend > 0 and price_trend > 0:
        sig = "价升量增 → 健康上涨"
    elif obv_trend < 0 and price_trend > 0:
        sig = "价升量减 → 顶背离 ⚠"
    elif obv_trend < 0 and price_trend < 0:
        sig = "价跌量减 → 下跌趋势"
    elif obv_trend > 0 and price_trend < 0:
        sig = "价跌量增 → 底背离 ★"
    else:
        sig = "量价同步"

    return {
        "obv_current": round(cur_obv, 0),
        "obv_ma5": round(obv_ma5, 0),
        "obv_trend": "上升" if obv_trend > 0 else "下降" if obv_trend < 0 else "走平",
        "signal": sig,
    }


def calc_cci(highs: list[float], lows: list[float], closes: list[float],
             period: int = 14) -> dict:
    """
    CCI 顺势指标——测量价格偏离统计平均的程度。
    CCI > +100 = 超买/强势启动，CCI < -100 = 超卖/弱势。
    ±200 为极端区域。
    """
    n = len(closes)
    if n < period:
        return {"cci": [], "signal": "数据不足"}

    tp = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(n)]
    cci_vals = []

    for i in range(period - 1, n):
        tp_slice = tp[i - period + 1:i + 1]
        tp_ma = sum(tp_slice) / period
        tp_md = sum(abs(t - tp_ma) for t in tp_slice) / period
        cci = (tp[i] - tp_ma) / (0.015 * tp_md) if tp_md > 0 else 0
        cci_vals.append(round(cci, 2))

    cur_cci = cci_vals[-1] if cci_vals else 0

    if cur_cci > 200:
        sig = "极端超买 🔴"
    elif cur_cci > 100:
        sig = "强势区 → 注意追高风险"
    elif cur_cci < -200:
        sig = "极端超卖 🟢"
    elif cur_cci < -100:
        sig = "弱势区 → 关注反弹机会"
    elif cur_cci > 0:
        sig = "偏强"
    else:
        sig = "偏弱"

    return {
        "cci_current": cur_cci,
        "cci_vals": cci_vals[-60:] if len(cci_vals) > 60 else cci_vals,
        "signal": sig,
    }


def calc_wr(highs: list[float], lows: list[float], closes: list[float],
            period: int = 14) -> dict:
    """
    WR 威廉指标——判断超买超卖的反向指标。
    WR < 20 = 超买(高估)，WR > 80 = 超卖(低估)。
    与KDJ互补使用效果更好。
    """
    n = len(closes)
    if n < period:
        return {"wr": [], "signal": "数据不足"}

    wr_vals = []
    for i in range(period - 1, n):
        hh = max(highs[i - period + 1:i + 1])
        ll = min(lows[i - period + 1:i + 1])
        wr = (hh - closes[i]) / (hh - ll) * 100 if hh != ll else 50
        wr_vals.append(round(wr, 2))

    cur_wr = wr_vals[-1] if wr_vals else 50

    if cur_wr > 80:
        sig = "超卖区 ★ 关注反弹"
    elif cur_wr < 20:
        sig = "超买区 ⚠ 注意回调"
    elif cur_wr > 50:
        sig = "偏弱"
    else:
        sig = "偏强"

    return {
        "wr_current": cur_wr,
        "wr_vals": wr_vals[-60:] if len(wr_vals) > 60 else wr_vals,
        "signal": sig,
    }


def calc_support_resistance(highs: list[float], lows: list[float],
                            closes: list[float]) -> dict:
    """
    支撑/阻力位自动识别——基于近期高低点和成交密集区。
    简单但实用的方法：近期高点的聚集体=阻力，低点的聚集体=支撑。
    """
    n = len(closes)
    if n < 20:
        return {"support": [], "resistance": [], "signal": "数据不足"}

    cur_price = closes[-1]

    # 找近期显著高点和低点
    lookback = min(60, n)
    recent_highs = []
    recent_lows = []
    for i in range(2, lookback - 2):
        idx = n - 1 - i
        if highs[idx] > highs[idx - 1] and highs[idx] > highs[idx - 2] and highs[idx] > highs[idx + 1] and highs[idx] > highs[idx + 2]:
            recent_highs.append(highs[idx])
        if lows[idx] < lows[idx - 1] and lows[idx] < lows[idx - 2] and lows[idx] < lows[idx + 1] and lows[idx] < lows[idx + 2]:
            recent_lows.append(lows[idx])

    # 聚类分析：相近的价格归为一组
    def cluster_levels(levels, threshold_pct=1.5):
        if not levels:
            return []
        levels = sorted(set(round(l, 2) for l in levels))
        clusters = []
        current = [levels[0]]
        for l in levels[1:]:
            if abs(l - current[-1]) / current[-1] * 100 < threshold_pct:
                current.append(l)
            else:
                clusters.append(round(sum(current) / len(current), 2))
                current = [l]
        if current:
            clusters.append(round(sum(current) / len(current), 2))
        return clusters

    supports = cluster_levels(recent_lows)
    resistances = cluster_levels(recent_highs)

    # 找最近的支撑和阻力
    nearest_support = max([s for s in supports if s < cur_price], default=cur_price * 0.95)
    nearest_resistance = min([r for r in resistances if r > cur_price], default=cur_price * 1.05)

    return {
        "support": supports[:5] if supports else [nearest_support],
        "resistance": resistances[:5] if resistances else [nearest_resistance],
        "nearest_support": round(nearest_support, 2),
        "nearest_resistance": round(nearest_resistance, 2),
        "support_pct": round((cur_price - nearest_support) / cur_price * 100, 2),
        "resistance_pct": round((nearest_resistance - cur_price) / cur_price * 100, 2),
        "signal": f"支撑{nearest_support:.2f}(-{(cur_price-nearest_support)/cur_price*100:.1f}%) | 阻力{nearest_resistance:.2f}(+{(nearest_resistance-cur_price)/cur_price*100:.1f}%)",
    }


def comprehensive_analysis(klines: list[dict]) -> dict:
    """
    综合技术分析——输入K线列表，输出所有技术指标的综合判断。
    这是接入 AI 分析前的核心数据预处理步骤。
    """
    if not klines or len(klines) < 10:
        return {"error": "K线数据不足"}

    closes = [k["close"] for k in klines]
    opens = [k["open"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    volumes = [k.get("volume", 0) for k in klines]

    return {
        "ma_system": calc_ma_system(closes),
        "macd": calc_macd(closes),
        "kdj": calc_kdj(highs, lows, closes),
        "rsi": calc_rsi(closes),
        "bollinger": calc_bollinger_bands(closes),
        "volume": calc_volume_analysis(volumes, closes),
        "atr": calc_atr(highs, lows, closes),
        "obv": calc_obv(closes, volumes),
        "cci": calc_cci(highs, lows, closes),
        "wr": calc_wr(highs, lows, closes),
        "sr_levels": calc_support_resistance(highs, lows, closes),
        "trend_summary": _generate_trend_summary(closes, highs, lows, volumes),
    }


def _generate_trend_summary(closes: list[float], highs: list[float],
                            lows: list[float], volumes: list[float]) -> dict:
    """生成趋势总结——综合各指标给出简洁判断。"""
    n = len(closes)
    if n < 20:
        return {"overall": "数据不足", "strength": 0}

    # 综合评分 (-100 ~ +100)
    score = 0

    # 均线排列 (+30/-30)
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60 if n >= 60 else ma20
    if closes[-1] > ma20 > ma60:
        score += 30
    elif closes[-1] < ma20 < ma60:
        score -= 30

    # RSI (+20/-20)
    rsi = calc_rsi(closes)
    if 40 <= rsi.get("rsi_current", 50) <= 60:
        score += 10
    elif rsi.get("rsi_current", 50) > 70:
        score -= 15
    elif rsi.get("rsi_current", 50) < 30:
        score += 15

    # 量价 (+20/-20)
    vol = calc_volume_analysis(volumes, closes)
    if "放量上涨" in vol.get("signal", ""):
        score += 20
    elif "放量下跌" in vol.get("signal", ""):
        score -= 20

    # 布林带位置 (+10/-10)
    bb = calc_bollinger_bands(closes)
    if closes[-1] >= bb.get("upper_current", 0) * 0.98:
        score -= 10
    elif closes[-1] <= bb.get("lower_current", 0) * 1.02:
        score += 10

    # 综合判断
    if score >= 40:
        overall = "强势多头"
    elif score >= 15:
        overall = "偏多震荡"
    elif score >= -15:
        overall = "横盘整理"
    elif score >= -40:
        overall = "偏空震荡"
    else:
        overall = "弱势空头"

    return {
        "overall": overall,
        "strength": score,
        "suggestion": _strength_suggestion(score),
    }


def _strength_suggestion(score: int) -> str:
    if score >= 40:
        return "趋势向好，可顺势持有或适度加仓"
    if score >= 15:
        return "短线偏多，关注量能配合"
    if score >= -15:
        return "方向不明，建议观望或轻仓"
    if score >= -40:
        return "偏弱，控制仓位，设置止损"
    return "弱势明显，减仓或观望为宜"
