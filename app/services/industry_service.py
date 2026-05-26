"""行业分类 & 风格暴露 & 行业轮动服务。"""
import time
from app.services.cache_service import cache_service

# 股票→行业映射（基于申万行业分类，覆盖220+只参照股）
STOCK_INDUSTRY = {}
STOCK_STYLE = {}

def _init():
    """初始化行业和风格映射。"""
    # 银行
    banks = ["601288","601398","601939","601988","601328","600016","600000","601818","600015","002142","600036","000001"]
    # 钢铁
    steels = ["600010","600022","600808","000709","000932","002075","000898","600019"]
    # 航空机场
    aviation = ["600221","601111","600029","600115"]
    # 电力
    power = ["600795","600027","600011","600023","601991","600900","600886","600674","000027","000883"]
    # 建筑
    construct = ["601618","601390","601668","601800","600170","002060","601186","601669","600820","002051"]
    # 有色
    metals = ["601899","600489","600547","600362","000630","000878","603993"]
    # 能源
    energy = ["600157","600256","000683","600028","601857","600688","000059","002493"]
    # 证券
    securities = ["600030","300059","601688","000776","000728","601211","600837","601377","000166","002736","000750","601878"]
    # 科技
    tech = ["000725","000100","002475","002415","600570","002230","603986","002049","688981","002371","603501","688111","002236","300124","688012","601360","300033","600588"]
    # 汽车
    auto = ["002594","600104","000625","000550","600006","000800","601238","600733","002920","601689","600660"]
    # 消费
    consumer = ["600519","000858","000568","600809","000596","002304","000799","603288","600887","002557","603899","600690","000651","000333","002242","002032"]
    # 医药
    pharma = ["603259","300760","600276","000661","300015","300122","603392","300347","300896","600518","002603","000538","600196","002001","600332"]
    # 地产
    realestate = ["000002","001979","600048","600383","000069"]
    # 农牧
    agriculture = ["002714","300498","002385","002157","000876"]
    # 传媒
    media = ["300413","002624","002739","600637","300251","600959","000156","002131"]
    # 建材
    building = ["600585","000401","002233","000786","002271"]
    # 服装
    textile = ["002563","600177","002029","002701"]

    for code in banks: STOCK_INDUSTRY[code] = "银行"; STOCK_STYLE[code] = "防御"
    for code in steels: STOCK_INDUSTRY[code] = "钢铁"; STOCK_STYLE[code] = "周期"
    for code in aviation: STOCK_INDUSTRY[code] = "交通运输"; STOCK_STYLE[code] = "周期"
    for code in power: STOCK_INDUSTRY[code] = "电力"; STOCK_STYLE[code] = "防御"
    for code in construct: STOCK_INDUSTRY[code] = "建筑"; STOCK_STYLE[code] = "周期"
    for code in metals: STOCK_INDUSTRY[code] = "有色金属"; STOCK_STYLE[code] = "周期"
    for code in energy: STOCK_INDUSTRY[code] = "能源"; STOCK_STYLE[code] = "周期"
    for code in securities: STOCK_INDUSTRY[code] = "证券"; STOCK_STYLE[code] = "周期"
    for code in tech: STOCK_INDUSTRY[code] = "科技"; STOCK_STYLE[code] = "成长"
    for code in auto: STOCK_INDUSTRY[code] = "汽车"; STOCK_STYLE[code] = "周期"
    for code in consumer: STOCK_INDUSTRY[code] = "消费"; STOCK_STYLE[code] = "防御"
    for code in pharma: STOCK_INDUSTRY[code] = "医药"; STOCK_STYLE[code] = "成长"
    for code in realestate: STOCK_INDUSTRY[code] = "房地产"; STOCK_STYLE[code] = "周期"
    for code in agriculture: STOCK_INDUSTRY[code] = "农林牧渔"; STOCK_STYLE[code] = "周期"
    for code in media: STOCK_INDUSTRY[code] = "传媒"; STOCK_STYLE[code] = "成长"
    for code in building: STOCK_INDUSTRY[code] = "建材"; STOCK_STYLE[code] = "周期"
    for code in textile: STOCK_INDUSTRY[code] = "纺织服装"; STOCK_STYLE[code] = "防御"

_init()


def get_industry(code: str) -> str:
    return STOCK_INDUSTRY.get(code, "其他")


def get_style(code: str) -> str:
    return STOCK_STYLE.get(code, "其他")


def analyze_exposure(positions: list[dict]) -> dict:
    """分析持仓的行业和风格暴露。positions=[{code,value},...]"""
    industries = {}
    styles = {}
    total_value = sum(p.get("value", 0) for p in positions) or 1

    for p in positions:
        code = p.get("code", "")
        value = p.get("value", 0)
        ind = get_industry(code)
        sty = get_style(code)
        industries[ind] = industries.get(ind, 0) + value
        styles[sty] = styles.get(sty, 0) + value

    # 行业集中度警告
    warnings = []
    for ind, val in industries.items():
        pct = val / total_value * 100
        if pct > 30:
            warnings.append(f"⚠ {ind}行业占比{pct:.0f}%，过于集中，建议≤25%")

    # 风格暴露
    style_pct = {k: round(v / total_value * 100, 1) for k, v in styles.items()}

    return {
        "industries": {k: round(v / total_value * 100, 1) for k, v in sorted(industries.items(), key=lambda x: x[1], reverse=True)},
        "styles": style_pct,
        "dominant_style": max(styles, key=styles.get) if styles else "未知",
        "warnings": warnings,
    }


def get_sector_rotation_hint(market_data: dict = None) -> dict:
    """行业轮动简单分析——基于近期涨跌判断当前市场风格。"""
    # 简化版：从当日各行业平均涨跌判断资金流向
    from app.services.data_service import data_service
    sectors = data_service.get_sector_performance()

    if not sectors:
        return {"note": "行业数据暂不可用", "leading": [], "lagging": []}

    leading = [s["name"] for s in sectors[:5]]
    lagging = [s["name"] for s in sectors[-3:]]
    avg_change = sum(s.get("change_pct", 0) for s in sectors) / max(len(sectors), 1)

    if avg_change > 1:
        bias = "资金整体流入，市场风险偏好较高"
    elif avg_change > 0:
        bias = "资金温和流入，结构性行情"
    elif avg_change > -1:
        bias = "资金小幅流出，观望情绪浓厚"
    else:
        bias = "资金明显流出，防御为主"

    return {
        "leading_sectors": leading,
        "lagging_sectors": lagging,
        "avg_sector_change": round(avg_change, 2),
        "capital_flow_bias": bias,
        "timestamp": time.strftime("%H:%M"),
    }
