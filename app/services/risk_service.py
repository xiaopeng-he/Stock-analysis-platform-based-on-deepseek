"""风险管理服务——VaR、最大回撤、夏普比率、贝塔、相关性、压力测试。"""
import math


def calc_max_drawdown(prices: list[float]) -> dict:
    """最大回撤——从峰值到谷底的最大跌幅。"""
    if len(prices) < 2:
        return {"mdd": 0, "mdd_pct": 0, "peak_idx": 0, "trough_idx": 0}
    peak = prices[0]; mdd = 0; peak_idx = trough_idx = 0; temp_peak_idx = 0
    for i, p in enumerate(prices):
        if p > peak:
            peak = p; temp_peak_idx = i
        dd = peak - p
        if dd > mdd:
            mdd = dd; peak_idx = temp_peak_idx; trough_idx = i
    return {"mdd": round(mdd, 2), "mdd_pct": round(mdd / peak * 100, 2) if peak else 0, "peak_idx": peak_idx, "trough_idx": trough_idx}


def calc_var(prices: list[float], confidence: float = 0.95) -> dict:
    """历史模拟法 VaR——在给定置信度下的最大可能亏损。"""
    if len(prices) < 10:
        return {"var_pct": 0, "var_amount": 0}
    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
    returns.sort()
    idx = int(len(returns) * (1 - confidence))
    var_pct = abs(returns[idx]) * 100 if idx < len(returns) else 0
    return {"var_pct": round(var_pct, 2), "var_amount": round(var_pct / 100 * prices[-1], 2), "confidence": confidence}


def calc_volatility(prices: list[float], annualize: bool = True) -> dict:
    """波动率——价格收益率的标准差，可年化。"""
    if len(prices) < 5:
        return {"daily_vol": 0, "annual_vol": 0}
    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
    mean = sum(returns) / len(returns) if returns else 0
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1) if len(returns) > 1 else 0
    daily = math.sqrt(variance)
    annual = daily * math.sqrt(252) if annualize else daily
    return {"daily_vol": round(daily * 100, 2), "annual_vol": round(annual * 100, 2)}


def calc_sharpe_approx(prices: list[float], risk_free: float = 0.02) -> dict:
    """夏普比率近似——(年化收益-无风险利率)/年化波动率。"""
    if len(prices) < 20:
        return {"sharpe": 0, "annual_return": 0, "annual_vol": 0}
    total_return = (prices[-1] - prices[0]) / prices[0] if prices[0] else 0
    days = len(prices)
    annual_return = (1 + total_return) ** (252 / days) - 1 if days > 0 else 0
    vol = calc_volatility(prices)
    annual_vol = vol["annual_vol"] / 100 if vol["annual_vol"] else 0.01
    sharpe = (annual_return - risk_free) / annual_vol if annual_vol else 0
    return {"sharpe": round(sharpe, 2), "annual_return": round(annual_return * 100, 2), "annual_vol": round(annual_vol * 100, 2), "risk_free": risk_free}


def calc_beta_approx(stock_prices: list[float], index_prices: list[float]) -> dict:
    """贝塔系数近似——个股相对大盘的波动敏感度。"""
    n = min(len(stock_prices), len(index_prices))
    if n < 10:
        return {"beta": 1.0, "note": "数据不足"}
    stock_returns = [(stock_prices[i] - stock_prices[i-1]) / stock_prices[i-1] for i in range(1, n)]
    index_returns = [(index_prices[i] - index_prices[i-1]) / index_prices[i-1] for i in range(1, n)]
    mean_s = sum(stock_returns) / len(stock_returns) if stock_returns else 0
    mean_i = sum(index_returns) / len(index_returns) if index_returns else 0
    cov = sum((stock_returns[i] - mean_s) * (index_returns[i] - mean_i) for i in range(len(stock_returns))) / (len(stock_returns) - 1) if len(stock_returns) > 1 else 0
    var_i = sum((r - mean_i) ** 2 for r in index_returns) / (len(index_returns) - 1) if len(index_returns) > 1 else 0
    beta = cov / var_i if var_i else 1.0
    interpretation = "防御型(低波动)" if beta < 0.8 else "中性" if beta < 1.2 else "进攻型(高波动)"
    return {"beta": round(beta, 2), "interpretation": interpretation}


def calc_correlation(stock1_prices: list[float], stock2_prices: list[float]) -> dict:
    """两只股票的相关系数。"""
    n = min(len(stock1_prices), len(stock2_prices))
    if n < 10:
        return {"correlation": 0, "note": "数据不足"}
    r1 = [(stock1_prices[i] - stock1_prices[i-1]) / stock1_prices[i-1] for i in range(1, n)]
    r2 = [(stock2_prices[i] - stock2_prices[i-1]) / stock2_prices[i-1] for i in range(1, n)]
    m1 = sum(r1) / len(r1); m2 = sum(r2) / len(r2)
    cov = sum((r1[i]-m1)*(r2[i]-m2) for i in range(len(r1))) / (len(r1)-1) if len(r1)>1 else 0
    std1 = math.sqrt(sum((r-m1)**2 for r in r1)/(len(r1)-1)) if len(r1)>1 else 1
    std2 = math.sqrt(sum((r-m2)**2 for r in r2)/(len(r2)-1)) if len(r2)>1 else 1
    corr = cov/(std1*std2) if std1 and std2 else 0
    level = "高度正相关" if corr>0.7 else "中度正相关" if corr>0.3 else "低相关" if corr>-0.3 else "中度负相关" if corr>-0.7 else "高度负相关"
    return {"correlation": round(corr, 2), "level": level}


def stress_test(prices: list[float], scenarios: list[float] = None) -> dict:
    """压力测试——在不同跌幅情景下的亏损。"""
    if scenarios is None:
        scenarios = [-5, -10, -20, -30]
    if not prices:
        return {"scenarios": []}
    current = prices[-1]
    results = []
    for s in scenarios:
        target = current * (1 + s / 100)
        loss = current - target
        results.append({"scenario": f"{s:+d}%", "target_price": round(target, 2), "loss": round(loss, 2), "loss_pct": abs(s)})
    return {"current_price": current, "scenarios": results}


def comprehensive_risk_report(stock_code: str, prices: list[float], index_prices: list[float] = None) -> dict:
    """综合风险报告。"""
    return {
        "max_drawdown": calc_max_drawdown(prices),
        "var_95": calc_var(prices, 0.95),
        "volatility": calc_volatility(prices),
        "sharpe": calc_sharpe_approx(prices),
        "beta": calc_beta_approx(prices, index_prices) if index_prices else {"beta": 1.0, "note": "无指数数据"},
        "stress_test": stress_test(prices),
    }
