"""数据采集服务——多数据源（腾讯 > 新浪 > akshare），自动降级，确保高可用。"""

import os
import re
import time
from typing import Optional

# ── 彻底禁用代理 ──
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"):
    os.environ[_k] = ""
os.environ["NO_PROXY"] = "*"

import requests as _requests
import urllib3
urllib3.disable_warnings()

# Monkey-patch: 强制所有 Session 请求跳过系统代理
_orig_request = _requests.Session.request


def _no_proxy_request(self, method, url, *args, **kwargs):
    self.trust_env = False
    kwargs.pop("proxies", None)
    return _orig_request(self, method, url, *args, **kwargs)


_requests.Session.request = _no_proxy_request

# 共享 Session——全局复用，提高连接效率
_session = _requests.Session()
_session.trust_env = False
_session.verify = False
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
})

import akshare as ak
import pandas as pd

from app.services.cache_service import cache_service

# ── 股票代码前缀映射 ──
_CODE_PREFIX_MAP = {
    "6": "sh", "5": "sh",  # 上海
    "0": "sz", "3": "sz", "2": "sz",  # 深圳
    "4": "bj", "8": "bj",  # 北京
}


def _code_to_sina(code: str) -> str:
    """将股票代码转为新浪API格式。"""
    p = _CODE_PREFIX_MAP.get(code[0], "sz")
    return f"{p}{code}"


def _code_to_tencent(code: str) -> str:
    """将股票代码转为腾讯API格式。"""
    p = _CODE_PREFIX_MAP.get(code[0], "sz")
    return f"{p}{code}"


def _fetch_url(url: str, referer: str = "", timeout: int = 8) -> Optional[str]:
    """通用 HTTP GET——自动检测编码（优先GBK，兜底UTF-8）。"""
    headers = {"Referer": referer} if referer else {}
    for attempt in range(2):
        try:
            r = _session.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                _fix_encoding(r)
                return r.text
            if r.status_code == 403:
                if len(r.text) > 50:
                    r.encoding = "gbk"
                    return r.text
            if r.status_code == 404:
                return None
        except Exception:
            if attempt == 0:
                time.sleep(0.5)
    return None


def _fix_encoding(r):
    """修正响应编码——国内财经数据源普遍使用GBK/GB2312。
    requests的apparent_encoding经常误判（如把GBK判为shift_jis），
    所以优先通过字节特征和URL来源判断。"""
    # 1) 已知的国内数据源——直接强制 GBK
    url = r.url or ""
    if any(d in url for d in ("gtimg.cn", "sinajs.cn", "sina.com.cn", "eastmoney.com", "10jqka.com")):
        r.encoding = "gbk"
        return
    # 2) Content-Type头明确指定
    ct = r.headers.get("Content-Type", "")
    if "charset=gb" in ct.lower():
        r.encoding = "gbk"
        return
    # 3) 字节特征检测——GBK/GB2312的高频字符
    raw = r.content[:500]
    # 统计 GBK 双字节序列的数量 (0x81-0xFE)(0x40-0xFE)
    gbk_count = 0
    i = 0
    while i < len(raw) - 1:
        if 0x81 <= raw[i] <= 0xFE and 0x40 <= raw[i+1] <= 0xFE:
            gbk_count += 1
            i += 2
        else:
            i += 1
    # 如果前500字节中有超过20个GBK双字节序列，极可能是GBK
    if gbk_count > 20:
        r.encoding = "gbk"
        return
    # 4) 退而求其次
    detected = r.apparent_encoding
    if detected and "gb" in detected.lower():
        r.encoding = "gbk"
    elif detected and detected.lower() in ("windows-1252", "iso-8859-1", "ascii", "shift_jis", "shift_jis_2004", "euc-jp"):
        r.encoding = "gbk"  # 中文数据源不可能是这些编码
    else:
        r.encoding = detected or "gbk"


class DataService:
    """A 股数据采集——多数据源自动降级。"""

    @staticmethod
    def _safe_float(val, default=0.0) -> float:
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    # ── 腾讯财经：实时行情 ──
    def _get_quote_tencent(self, stock_code: str) -> Optional[dict]:
        """从腾讯财经获取单只股票实时行情。"""
        tcode = _code_to_tencent(stock_code)
        text = _fetch_url(f"http://qt.gtimg.cn/q={tcode}", "https://gu.qq.com/")
        if not text:
            return None
        # 腾讯格式: v_sh600519="1~贵州茅台~600519~..."
        text = text.strip()
        if "~" not in text:
            return None
        parts = text.split("~")
        if len(parts) < 40:
            return None
        try:
            p = parts
            return {
                "code": stock_code,
                "name": p[1],
                "price": self._safe_float(p[3]),
                "change_pct": self._safe_float(p[32]),
                "change_amount": self._safe_float(p[31]),
                "volume": self._safe_float(p[6]) * 100,  # 腾讯是手，转为股
                "amount": self._safe_float(p[37]) * 10000,
                "high": self._safe_float(p[33]),
                "low": self._safe_float(p[34]),
                "open": self._safe_float(p[5]),
                "pre_close": self._safe_float(p[4]),
                "turnover": self._safe_float(p[38]),
                "pe": self._safe_float(p[39]),
            }
        except (IndexError, ValueError):
            return None

    # ── 新浪财经：实时行情 ──
    def _get_quote_sina(self, stock_code: str) -> Optional[dict]:
        """从新浪财经获取单只股票实时行情。"""
        scode = _code_to_sina(stock_code)
        text = _fetch_url(f"https://hq.sinajs.cn/list={scode}", "https://finance.sina.com.cn/")
        if not text or "=" not in text:
            return None
        try:
            data = text.split('"')[1]
            parts = data.split(",")
            if len(parts) < 30:
                return None
            return {
                "code": stock_code,
                "name": parts[0],
                "price": self._safe_float(parts[3]),
                "change_pct": self._safe_float(parts[3]) / self._safe_float(parts[2]) * 100 - 100 if self._safe_float(parts[2]) else 0,
                "change_amount": self._safe_float(parts[3]) - self._safe_float(parts[2]),
                "volume": self._safe_float(parts[8]),
                "amount": self._safe_float(parts[9]) * 10000,
                "high": self._safe_float(parts[4]),
                "low": self._safe_float(parts[5]),
                "open": self._safe_float(parts[1]),
                "pre_close": self._safe_float(parts[2]),
                "turnover": 0,  # 新浪无换手率
                "pe": 0,
            }
        except (IndexError, ValueError):
            return None

    # ── 批量行情：一次请求拉取多只股票（性能提升核心） ──
    def get_batch_quotes(self, stock_codes: list[str]) -> dict[str, dict]:
        """
        批量获取实时行情——腾讯API支持一次请求最多~50只股票。
        比逐个调用快 10-50 倍，是首页加载和自选股列表的核心优化。
        """
        if not stock_codes:
            return {}

        # 先检查缓存
        results = {}
        uncached = []
        for code in stock_codes:
            cached = cache_service.get(f"quote:{code}")
            if cached:
                results[code] = cached
            else:
                uncached.append(code)

        if not uncached:
            return results

        # 腾讯批量API（一次最多约50只）
        for batch_start in range(0, len(uncached), 50):
            batch = uncached[batch_start:batch_start + 50]
            tcodes = [_code_to_tencent(c) for c in batch]
            # 腾讯格式: sh600519,sz000001,...
            tcode_str = ",".join(tcodes)
            text = _fetch_url(f"http://qt.gtimg.cn/q={tcode_str}", "https://gu.qq.com/")

            if text:
                for line in text.strip().split("\n"):
                    if "~" not in line or "=" not in line:
                        continue
                    try:
                        tag = line.split("=")[0].strip()
                        data = line.split('"')[1] if '"' in line else line.split("=")[1]
                        parts = data.split("~")
                        if len(parts) < 40:
                            continue
                        p = parts
                        code = p[2]
                        quote = {
                            "code": code,
                            "name": p[1],
                            "price": self._safe_float(p[3]),
                            "change_pct": self._safe_float(p[32]),
                            "change_amount": self._safe_float(p[31]),
                            "volume": self._safe_float(p[6]) * 100,
                            "amount": self._safe_float(p[37]) * 10000,
                            "high": self._safe_float(p[33]),
                            "low": self._safe_float(p[34]),
                            "open": self._safe_float(p[5]),
                            "pre_close": self._safe_float(p[4]),
                            "turnover": self._safe_float(p[38]),
                            "pe": self._safe_float(p[39]),
                        }
                        cache_service.set(f"quote:{code}", quote, ttl=5)
                        results[code] = quote
                    except (IndexError, ValueError):
                        continue

        return results

    # ── 统一入口：多数据源自动降级 ──
    def get_realtime_quote(self, stock_code: str) -> Optional[dict]:
        """获取单只股票实时行情——腾讯→新浪→akshare 自动降级。"""
        cache_key = f"quote:{stock_code}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        # 优先级: akshare（数据最全） > 腾讯 > 新浪
        for name, fetcher in [
            ("akshare", self._get_quote_akshare),
            ("tencent", self._get_quote_tencent),
            ("sina", self._get_quote_sina),
        ]:
            try:
                result = fetcher(stock_code)
                if result:
                    cache_service.set(cache_key, result, ttl=5)
                    return result
            except Exception as e:
                print(f"[DataService] {name} quote failed for {stock_code}: {e}")
                continue

        return cached  # 返回过期缓存作为降级

    def _get_quote_akshare(self, stock_code: str) -> Optional[dict]:
        """akshare 获取单只股票行情（原实现）。"""
        try:
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == stock_code]
            if row.empty:
                return None
            r = row.iloc[0]
            return {
                "code": stock_code,
                "name": str(r["名称"]),
                "price": self._safe_float(r.get("最新价")),
                "change_pct": self._safe_float(r.get("涨跌幅")),
                "change_amount": self._safe_float(r.get("涨跌额")),
                "volume": self._safe_float(r.get("成交量")),
                "amount": self._safe_float(r.get("成交额")),
                "high": self._safe_float(r.get("最高")),
                "low": self._safe_float(r.get("最低")),
                "open": self._safe_float(r.get("今开")),
                "pre_close": self._safe_float(r.get("昨收")),
                "turnover": self._safe_float(r.get("换手率")),
                "pe": self._safe_float(r.get("市盈率-动态")),
            }
        except Exception:
            return None

    def search_stock(self, keyword: str) -> list[dict]:
        """按关键词搜索股票——akshare 失败时降级到热门股票表 + 腾讯单股查询。"""
        cache_key = f"search:{keyword}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        results = []
        # 优先用 akshare 全市场搜索
        try:
            df = ak.stock_zh_a_spot_em()
            df = df[df["名称"].str.contains(keyword, na=False) | df["代码"].str.contains(keyword, na=False)]
            for _, r in df.head(20).iterrows():
                results.append({
                    "code": r["代码"],
                    "name": r["名称"],
                    "price": self._safe_float(r.get("最新价")),
                    "change_pct": self._safe_float(r.get("涨跌幅")),
                })
        except Exception as e:
            print(f"[DataService] akshare search failed: {e}, using fallback")
            # 降级1：热门股票表搜索
            from app.services.stock_reference import search_popular
            ref_results = search_popular(keyword, limit=10)
            for r in ref_results:
                quote = self.get_realtime_quote(r["code"])
                r["price"] = quote["price"] if quote else 0
                r["change_pct"] = quote["change_pct"] if quote else 0
                results.append(r)
            # 降级2：尝试腾讯以代码查询
            if not results:
                quote = self.get_realtime_quote(keyword)
                if quote:
                    results = [{
                        "code": keyword,
                        "name": quote["name"],
                        "price": quote["price"],
                        "change_pct": quote["change_pct"],
                    }]

        # 补充各股票的实时价格
        for r in results:
            if not r.get("price"):
                q = self.get_realtime_quote(r["code"])
                if q:
                    r["price"] = q["price"]
                    r["change_pct"] = q["change_pct"]

        cache_service.set(cache_key, results, ttl=30)
        return results

    def get_market_overview(self) -> dict:
        """获取大盘指数概览——腾讯API（稳定可靠）。"""
        cache_key = "market_overview"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        indices = {}
        index_map = [
            ("s_sh000001", "上证指数"),
            ("s_sz399001", "深证成指"),
            ("s_sz399006", "创业板指"),
            ("s_sh000688", "科创50"),
        ]
        codes_str = ",".join(c[0] for c in index_map)
        text = _fetch_url(f"http://qt.gtimg.cn/q={codes_str}", "https://gu.qq.com/")
        if text:
            name_map = dict(index_map)
            for line in text.strip().split("\n"):
                if "~" not in line:
                    continue
                try:
                    p = line.split("~")
                    code_raw = p[2] if len(p) > 2 else ""
                    full_name = name_map.get(f"s_sh{code_raw}", name_map.get(f"s_sz{code_raw}", ""))
                    if not full_name:
                        # 用 key 匹配
                        for k, v in name_map.items():
                            if code_raw in k:
                                full_name = v
                                break
                    if not full_name:
                        continue
                    indices[full_name] = {
                        "code": code_raw,
                        "price": self._safe_float(p[3]),
                        "change_pct": self._safe_float(p[5]),
                        "change_amount": self._safe_float(p[4]),
                    }
                except (IndexError, ValueError):
                    continue

        # 降级：新浪
        if not indices:
            sina_map = [
                ("s_sh000001", "上证指数"),
                ("s_sz399001", "深证成指"),
                ("s_sz399006", "创业板指"),
            ]
            scodes = ",".join(c[0] for c in sina_map)
            stext = _fetch_url(f"https://hq.sinajs.cn/list={scodes}", "https://finance.sina.com.cn/")
            if stext:
                snames = dict(sina_map)
                for line in stext.strip().split("\n"):
                    if '="' not in line:
                        continue
                    try:
                        code_tag = line.split("=")[0].replace("var hq_str_", "")
                        data = line.split('"')[1].split(",")
                        if len(data) < 4:
                            continue
                        idx_name = snames.get(code_tag, "")
                        if not idx_name:
                            continue
                        price = self._safe_float(data[1])
                        indices[idx_name] = {
                            "code": code_tag.replace("s_sh", "").replace("s_sz", ""),
                            "price": price,
                            "change_pct": self._safe_float(data[3]),
                            "change_amount": self._safe_float(data[2]),
                        }
                    except (IndexError, ValueError):
                        continue

        if indices:
            cache_service.set(cache_key, indices, ttl=15)
        return indices

    def get_minute_kline(self, stock_code: str, period: str = "5") -> list[dict]:
        """获取分钟级 K 线数据——新浪API → akshare 自动降级。"""
        cache_key = f"kline:{stock_code}:{period}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        # 优先：akshare（数据更完整）
        try:
            df = ak.stock_zh_a_hist_min_em(symbol=stock_code, period=period, adjust="")
            if not df.empty:
                klines = []
                for _, r in df.tail(120).iterrows():
                    klines.append({
                        "time": str(r.get("时间", "")),
                        "open": self._safe_float(r.get("开盘")),
                        "close": self._safe_float(r.get("收盘")),
                        "high": self._safe_float(r.get("最高")),
                        "low": self._safe_float(r.get("最低")),
                        "volume": self._safe_float(r.get("成交量")),
                    })
                cache_service.set(cache_key, klines, ttl=60)
                return klines
        except Exception:
            pass  # 降级到新浪

        # 降级：新浪 K 线 API
        scode = _code_to_sina(stock_code)
        try:
            import json
            url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={scode}&scale={period}&ma=no&datalen=120"
            text = _fetch_url(url, "https://finance.sina.com.cn/", timeout=10)
            if text:
                raw = json.loads(text)
                klines = []
                for r in raw[-120:]:
                    klines.append({
                        "time": r.get("day", ""),
                        "open": self._safe_float(r.get("open")),
                        "close": self._safe_float(r.get("close")),
                        "high": self._safe_float(r.get("high")),
                        "low": self._safe_float(r.get("low")),
                        "volume": self._safe_float(r.get("volume")),
                    })
                if klines:
                    cache_service.set(cache_key, klines, ttl=60)
                    return klines
        except Exception as e:
            print(f"[DataService] sina kline also failed for {stock_code}: {e}")

        return cached or []

    def get_daily_kline(self, stock_code: str) -> list[dict]:
        """获取日K线数据——腾讯API。"""
        cache_key = f"kline:daily:{stock_code}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        try:
            scode = _code_to_sina(stock_code)
            import json
            url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={scode}&scale=240&ma=no&datalen=120"
            text = _fetch_url(url, "https://finance.sina.com.cn/", timeout=10)
            if text:
                raw = json.loads(text)
                klines = []
                for r in raw[-120:]:
                    klines.append({
                        "time": r.get("day", ""),
                        "open": self._safe_float(r.get("open")),
                        "close": self._safe_float(r.get("close")),
                        "high": self._safe_float(r.get("high")),
                        "low": self._safe_float(r.get("low")),
                        "volume": self._safe_float(r.get("volume")),
                    })
                cache_service.set(cache_key, klines, ttl=300)
                return klines
        except Exception as e:
            print(f"[DataService] daily kline error for {stock_code}: {e}")
        return []

    def get_stock_news(self, stock_code: str, limit: int = 10) -> list[dict]:
        """获取个股相关新闻。"""
        cache_key = f"news:{stock_code}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        try:
            # 使用 akshare 的 stock_news_em 获取个股新闻
            df = ak.stock_news_em(symbol=stock_code)
            if df.empty:
                return []
            news_list = []
            for _, r in df.head(limit).iterrows():
                news_list.append({
                    "title": str(r.get("新闻标题", "")),
                    "source": str(r.get("文章来源", "")),
                    "time": str(r.get("发布时间", "")),
                    "url": str(r.get("新闻链接", "")),
                })
            cache_service.set(cache_key, news_list, ttl=300)
            return news_list
        except Exception:
            # stock_news_em 可能不可用，尝试用 stock_info_global_em 等其他接口
            try:
                df = ak.stock_info_global_em(symbol=stock_code)
                if not df.empty:
                    # stock_info_global_em 返回结构不同，尝试提取可用信息
                    news_list = []
                    for _, r in df.head(limit).iterrows():
                        title = str(r.iloc[0]) if len(r) > 0 else ""
                        if title:
                            news_list.append({
                                "title": title,
                                "source": "东方财富",
                                "time": str(r.iloc[-1]) if len(r) > 1 else "",
                                "url": "",
                            })
                    if news_list:
                        cache_service.set(cache_key, news_list, ttl=300)
                        return news_list
            except Exception:
                pass
            return []

    def get_market_news(self, limit: int = 15) -> list[dict]:
        """获取 A 股市场要闻。"""
        cache_key = "market_news"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        try:
            df = ak.stock_info_global_em(symbol="A股")
            news_list = []
            for _, r in df.head(limit).iterrows():
                news_list.append({
                    "title": str(r.get("新闻标题", r.iloc[0] if len(r) > 0 else "")),
                    "source": str(r.get("文章来源", r.iloc[1] if len(r) > 1 else "东方财富")),
                    "time": str(r.get("发布时间", "")),
                    "url": str(r.get("新闻链接", "")),
                })
            cache_service.set(cache_key, news_list, ttl=300)
            return news_list
        except Exception as e:
            print(f"[DataService] get_market_news error: {e}")
            return []

    # ── 以下为 v0.2 新增：一键推荐所需的市场全景数据 ──

    def get_top_gainers(self, top_n: int = 30) -> list[dict]:
        """获取涨幅榜前 N 名。"""
        cache_key = f"top_gainers:{top_n}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached
        try:
            df = ak.stock_zh_a_spot_em()
            df = df.sort_values("涨跌幅", ascending=False).head(top_n)
            results = []
            for _, r in df.iterrows():
                results.append({
                    "code": str(r["代码"]),
                    "name": str(r["名称"]),
                    "price": self._safe_float(r.get("最新价")),
                    "change_pct": self._safe_float(r.get("涨跌幅")),
                    "volume": self._safe_float(r.get("成交量")),
                    "turnover": self._safe_float(r.get("换手率")),
                    "pe": self._safe_float(r.get("市盈率-动态")),
                })
            cache_service.set(cache_key, results, ttl=30)
            return results
        except Exception as e:
            print(f"[DataService] get_top_gainers error: {e}")
            return []

    def get_top_losers(self, top_n: int = 30) -> list[dict]:
        """获取跌幅榜前 N 名。"""
        cache_key = f"top_losers:{top_n}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached
        try:
            df = ak.stock_zh_a_spot_em()
            df = df.sort_values("涨跌幅", ascending=True).head(top_n)
            results = []
            for _, r in df.iterrows():
                results.append({
                    "code": str(r["代码"]),
                    "name": str(r["名称"]),
                    "price": self._safe_float(r.get("最新价")),
                    "change_pct": self._safe_float(r.get("涨跌幅")),
                })
            cache_service.set(cache_key, results, ttl=30)
            return results
        except Exception as e:
            print(f"[DataService] get_top_losers error: {e}")
            return []

    def get_sector_performance(self) -> list[dict]:
        """获取行业板块涨跌幅排行——akshare失败时用腾讯板块接口。"""
        cache_key = "sector_perf"
        cached = cache_service.get(cache_key)
        if cached:
            return cached
        try:
            df = ak.stock_board_industry_name_em()
            results = []
            for _, r in df.head(30).iterrows():
                results.append({
                    "name": str(r.get("板块名称", "")),
                    "change_pct": self._safe_float(r.get("涨跌幅")),
                    "up_count": self._safe_float(r.get("上涨家数")),
                    "down_count": self._safe_float(r.get("下跌家数")),
                    "leader": str(r.get("领涨股票", "")),
                    "leader_pct": self._safe_float(r.get("领涨股票-涨跌幅")),
                })
            results.sort(key=lambda x: x["change_pct"], reverse=True)
            cache_service.set(cache_key, results, ttl=60)
            return results
        except Exception as e:
            print(f"[DataService] akshare sector failed, using tencent fallback: {e}")

        # 降级：腾讯行业板块
        try:
            text = _fetch_url("http://qt.gtimg.cn/q=pt000100,pt000200,pt000300,pt000400,pt000500,pt000600,pt000700,pt000800,pt000900,pt001000", "https://gu.qq.com/")
            if text:
                results = []
                for line in text.strip().split("\n"):
                    if "~" not in line:
                        continue
                    p = line.split("~")
                    if len(p) > 5:
                        results.append({
                            "name": p[1] if len(p) > 1 else "",
                            "change_pct": self._safe_float(p[5]) if len(p) > 5 else 0,
                            "up_count": 0,
                            "down_count": 0,
                            "leader": p[4] if len(p) > 4 else "",
                            "leader_pct": 0,
                        })
                results.sort(key=lambda x: x["change_pct"], reverse=True)
                cache_service.set(cache_key, results, ttl=60)
                return results
        except Exception as e2:
            print(f"[DataService] tencent sector also failed: {e2}")
        return []

    def get_concept_performance(self) -> list[dict]:
        """获取热门概念板块排行——akshare失败时尝试腾讯概念板块。"""
        cache_key = "concept_perf"
        cached = cache_service.get(cache_key)
        if cached:
            return cached
        try:
            df = ak.stock_board_concept_name_em()
            results = []
            for _, r in df.head(25).iterrows():
                results.append({
                    "name": str(r.get("板块名称", "")),
                    "change_pct": self._safe_float(r.get("涨跌幅")),
                    "up_count": self._safe_float(r.get("上涨家数")),
                    "leader": str(r.get("领涨股票", "")),
                })
            results.sort(key=lambda x: x["change_pct"], reverse=True)
            cache_service.set(cache_key, results, ttl=60)
            return results
        except Exception as e:
            print(f"[DataService] akshare concept failed: {e}, using tencent fallback")
        # 降级：腾讯概念板块
        try:
            text = _fetch_url("http://qt.gtimg.cn/q=pt800100,pt800200,pt800300,pt800400,pt800500,pt800600,pt800700,pt800800", "https://gu.qq.com/")
            if text:
                results = []
                for line in text.strip().split("\n"):
                    if "~" not in line:
                        continue
                    p = line.split("~")
                    if len(p) > 5:
                        results.append({
                            "name": p[1] if len(p) > 1 else "",
                            "change_pct": self._safe_float(p[5]) if len(p) > 5 else 0,
                            "up_count": 0,
                            "leader": "",
                        })
                results.sort(key=lambda x: x["change_pct"], reverse=True)
                cache_service.set(cache_key, results, ttl=60)
                return results
        except Exception as e2:
            print(f"[DataService] tencent concept also failed: {e2}")
        return []

    def get_north_flow(self) -> dict:
        """获取北向资金流向——akshare失败时返回合理默认值。"""
        cache_key = "north_flow"
        cached = cache_service.get(cache_key)
        if cached:
            return cached
        try:
            df = ak.stock_hsgt_hist_em(symbol="北向资金")
            if df.empty:
                return {"today": 0, "recent_days": []}
            recent = df.tail(10)
            today_val = self._safe_float(recent.iloc[-1].get("净买入"))
            history = []
            for _, r in recent.iterrows():
                history.append({
                    "date": str(r.get("日期", "")),
                    "net_flow": self._safe_float(r.get("净买入")),
                })
            result = {"today": today_val, "recent_days": history}
            cache_service.set(cache_key, result, ttl=120)
            return result
        except Exception as e:
            print(f"[DataService] get_north_flow error: {e}")
            # 返回合理默认值而非空
            return {"today": 0, "recent_days": [], "note": "数据暂不可用"}

    def get_limit_up_pool(self) -> list[dict]:
        """获取涨停板股票池。"""
        cache_key = "limit_up"
        cached = cache_service.get(cache_key)
        if cached:
            return cached
        try:
            df = ak.stock_zt_pool_em(date="")
            results = []
            for _, r in df.head(50).iterrows():
                results.append({
                    "code": str(r.get("代码", "")),
                    "name": str(r.get("名称", "")),
                    "change_pct": self._safe_float(r.get("涨跌幅")),
                    "limit_times": self._safe_float(r.get("连板数")),
                    "turnover": self._safe_float(r.get("换手率")),
                    "reason": str(r.get("涨停原因", "")) if "涨停原因" in df.columns else "",
                })
            cache_service.set(cache_key, results, ttl=60)
            return results
        except Exception as e:
            print(f"[DataService] get_limit_up_pool error: {e}")
            return []

    def get_all_market_data(self) -> dict:
        """一键获取全市场分析所需的全部数据——推荐功能的底层。"""
        return {
            "indices": self.get_market_overview(),
            "top_gainers": self.get_top_gainers(30),
            "top_losers": self.get_top_losers(10),
            "sectors": self.get_sector_performance(),
            "concepts": self.get_concept_performance(),
            "north_flow": self.get_north_flow(),
            "limit_up": self.get_limit_up_pool(),
            "market_news": self.get_market_news(8),
            "market_time": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
        }


data_service = DataService()
