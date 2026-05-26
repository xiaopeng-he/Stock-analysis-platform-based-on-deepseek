"""定时调度服务——交易时段检测、定时任务管理。"""

import datetime
import threading
import time
import logging

from app.config import config
from app.services.data_service import data_service

logger = logging.getLogger(__name__)


def is_trading_time() -> bool:
    """判断当前是否在 A 股交易时段（周一至周五 9:30-11:30, 13:00-15:00）。"""
    now = datetime.datetime.now()

    # 周末不交易
    if now.weekday() >= 5:
        return False

    t = (now.hour, now.minute)
    morning = (
        t >= config.TRADING_MORNING_START and t < config.TRADING_MORNING_END
    )
    afternoon = (
        t >= config.TRADING_AFTERNOON_START and t < config.TRADING_AFTERNOON_END
    )
    return morning or afternoon


def get_trading_status() -> dict:
    """获取当前交易状态信息。"""
    if is_trading_time():
        return {"status": "trading", "label": "交易中"}
    now = datetime.datetime.now()
    if now.weekday() >= 5:
        return {"status": "weekend", "label": "周末休市"}

    t = (now.hour, now.minute)
    if t < config.TRADING_MORNING_START:
        return {"status": "pre_market", "label": "盘前"}
    if config.TRADING_MORNING_END <= t < config.TRADING_AFTERNOON_START:
        return {"status": "lunch_break", "label": "午间休市"}
    if t >= config.TRADING_AFTERNOON_END:
        return {"status": "closed", "label": "已收盘"}
    return {"status": "unknown", "label": ""}


class SchedulerService:
    """后台定时任务调度器。"""

    def __init__(self):
        self._running = False
        self._thread = None

    def start(self):
        """启动后台调度线程。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("[Scheduler] Started")

    def stop(self):
        """停止调度。"""
        self._running = False
        logger.info("[Scheduler] Stopped")

    def _run(self):
        """后台循环——按交易时段调整采集频率。"""
        while self._running:
            try:
                if is_trading_time():
                    # 交易时段：积极采集
                    time.sleep(5)
                else:
                    # 非交易时段：悠闲等待
                    time.sleep(60)
            except Exception as e:
                logger.warning(f"[Scheduler] error: {e}")
                time.sleep(10)


scheduler_service = SchedulerService()
