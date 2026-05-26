"""缓存服务——内存 dict + SQLite 双缓存，减少 API 重复调用。"""

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional


class CacheService:
    """线程安全的双层缓存：内存（热数据，极速）+ SQLite（温数据，持久化）。"""

    def __init__(self):
        self._memory: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()
        db_path = Path(__file__).parent.parent.parent / "data" / "cache.db"
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, expire_at REAL)"
        )
        self._conn.commit()

    def get(self, key: str) -> Optional[object]:
        """读取缓存，先查内存再查 SQLite，过期返回 None。"""
        now = time.time()

        # Level 1: 内存
        with self._lock:
            entry = self._memory.get(key)
            if entry is not None:
                expire_at, val = entry
                if now < expire_at:
                    return val
                del self._memory[key]

        # Level 2: SQLite
        try:
            cur = self._conn.execute(
                "SELECT value, expire_at FROM cache WHERE key = ?", (key,)
            )
            row = cur.fetchone()
            if row:
                value_str, expire_at = row
                if now < expire_at:
                    val = json.loads(value_str)
                    with self._lock:
                        self._memory[key] = (expire_at, val)
                    return val
                self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                self._conn.commit()
        except Exception as e:
            print(f"[CacheService] error reading {key}: {e}")

        return None

    def set(self, key: str, value: object, ttl: int = 60):
        """写入双层缓存。"""
        expire_at = time.time() + ttl
        value_str = json.dumps(value, ensure_ascii=False, default=str)

        # 写入内存
        with self._lock:
            self._memory[key] = (expire_at, value)

        # 写入 SQLite
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expire_at) VALUES (?, ?, ?)",
                (key, value_str, expire_at),
            )
            self._conn.commit()
        except Exception as e:
            print(f"[CacheService] error writing {key}: {e}")

    def invalidate(self, key_prefix: str):
        """清除匹配前缀的缓存。"""
        with self._lock:
            keys_to_del = [k for k in self._memory if k.startswith(key_prefix)]
            for k in keys_to_del:
                del self._memory[k]
        try:
            self._conn.execute(
                "DELETE FROM cache WHERE key LIKE ?", (f"{key_prefix}%",)
            )
            self._conn.commit()
        except Exception as e:
            print(f"[CacheService] error invalidating {key_prefix}: {e}")

    def clear_memory(self):
        """仅清空内存缓存。"""
        with self._lock:
            self._memory.clear()


cache_service = CacheService()
