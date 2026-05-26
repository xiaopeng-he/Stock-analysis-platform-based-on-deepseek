"""API 频率限制器——控制 DeepSeek API 调用频率。"""

import time
import threading
from collections import defaultdict


class RateLimiter:
    """简单的内存频率限制器，防止 API 调用过于频繁。"""

    def __init__(self):
        self._timestamps: dict[str, float] = {}
        self._lock = threading.Lock()

    def check(self, key: str, interval_sec: float = 60) -> bool:
        """
        检查是否允许本次调用。
        - 返回 True: 允许调用
        - 返回 False: 调用被限制
        """
        now = time.time()
        with self._lock:
            last = self._timestamps.get(key)
            if last is None or (now - last) >= interval_sec:
                self._timestamps[key] = now
                return True
            return False

    def reset(self, key: str):
        """清除特定 key 的限制记录。"""
        with self._lock:
            self._timestamps.pop(key, None)


rate_limiter = RateLimiter()
