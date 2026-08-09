"""限速 / 去重 / 历史过滤等基础设施工具。"""

from __future__ import annotations

import asyncio
import time

from core.logger import get_logger


class RateLimiter:
    """令牌式间隔限速器。

    保证两次调用之间至少间隔 ``interval`` 秒。
    线程安全：内部使用 asyncio.Lock。
    """

    def __init__(self, interval: float = 0.0) -> None:
        self.interval = max(interval, 0.0)
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """等待直到可以发起下一次请求。"""
        async with self._lock:
            now = time.monotonic()
            wait = self._last + self.interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


class Deduplicator:
    """消息 ID 去重器。

    服务器可能重复返回同一消息（轮询/Socket.IO 双通道、重连补发）。
    维护一个定长集合，超限时裁剪保留最近一半。

    Attributes:
        max_size: 集合上限，默认 2000。
        trim_size: 超限后裁剪到的规模，默认 1000。
    """

    def __init__(self, max_size: int = 2000, trim_size: int = 1000) -> None:
        self.max_size = max_size
        self.trim_size = trim_size
        self._seen: set[int | str] = set()
        self._logger = get_logger("limits")

    def seen(self, msg_id: int | str) -> bool:
        """是否已处理过该消息 ID。"""
        return msg_id in self._seen

    def mark(self, msg_id: int | str) -> None:
        """标记消息 ID 为已处理，必要时裁剪集合。"""
        self._seen.add(msg_id)
        if len(self._seen) > self.max_size:
            trimmed = set(list(self._seen)[-self.trim_size:])
            self._logger.debug("去重集合超限，裁剪 %d -> %d", len(self._seen), len(trimmed))
            self._seen = trimmed

    def check_and_mark(self, msg_id: int | str) -> bool:
        """原子操作：若未处理则标记并返回 True，否则返回 False。"""
        if self.seen(msg_id):
            return False
        self.mark(msg_id)
        return True

    def clear(self) -> None:
        self._seen.clear()


class HistoryFilter:
    """历史消息过滤器。

    机器人加入房间前服务器可能返回的历史消息一律忽略。
    """

    def __init__(self) -> None:
        self.join_time: float = 0.0

    def mark_joined(self, t: float | None = None) -> None:
        """记录加入时刻。"""
        self.join_time = t or time.time()

    def is_old(self, msg_time: float) -> bool:
        """消息时间是否早于加入时刻。"""
        return bool(msg_time) and msg_time < self.join_time
