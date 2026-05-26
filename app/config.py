"""应用配置——从环境变量读取，管理所有可配置项。"""

import os

# ── 关键：优先清除可能存在的代理设置（国内访问东方财富等数据源不需要代理）──
# requests 库在 Windows 上会自动读取系统代理，这里显式清空确保能直连
for _key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    if not os.getenv(_key):
        os.environ[_key] = ""
os.environ.setdefault("NO_PROXY", "eastmoney.com,10jqka.com,sina.com.cn,qq.com")
os.environ.setdefault("no_proxy", "eastmoney.com,10jqka.com,sina.com.cn,qq.com")

from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── DeepSeek API ──
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # ── 服务 ──
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # ── 缓存 TTL（秒） ──
    CACHE_PRICE_TTL: int = int(os.getenv("CACHE_PRICE_TTL", "3"))
    CACHE_AI_TTL: int = int(os.getenv("CACHE_AI_TTL", "60"))
    CACHE_NEWS_TTL: int = int(os.getenv("CACHE_NEWS_TTL", "300"))

    # ── 数据库 ──
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'astock.db')}",
    )

    # ── A股交易时段（北京时间） ──
    TRADING_MORNING_START: tuple = (9, 30)
    TRADING_MORNING_END: tuple = (11, 30)
    TRADING_AFTERNOON_START: tuple = (13, 0)
    TRADING_AFTERNOON_END: tuple = (15, 0)


config = Config()
