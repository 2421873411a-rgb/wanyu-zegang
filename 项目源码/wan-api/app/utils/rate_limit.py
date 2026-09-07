"""应用内滑动窗口限流器（v17.9.1 S2）。

适用范围说明：进程内实现，单 worker / 少量 worker 场景够用；
Gunicorn 多 worker 下各进程独立计数，防爆破强度按 worker 数稀释——
上 Redis 前先保持 worker 数有限，或把强度调严。将来接入 REDIS_URL 原位替换。
"""
import time
from collections import defaultdict, deque
from threading import Lock


class RateLimiter:
    def __init__(self, max_events: int, window_seconds: float):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        """当前窗口内事件数未超限时返回 True（不记录新事件）。"""
        now = time.monotonic()
        with self._lock:
            q = self._events.get(key)
            if q is None:
                return True
            while q and now - q[0] > self.window_seconds:
                q.popleft()
            return len(q) < self.max_events

    def hit(self, key: str) -> None:
        """记录一次事件。"""
        now = time.monotonic()
        with self._lock:
            q = self._events[key]
            q.append(now)
            while q and now - q[0] > self.window_seconds:
                q.popleft()

    def clear(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def reset(self) -> None:
        """清空全部状态（测试用）。"""
        with self._lock:
            self._events.clear()


# 登录/注册防爆破：同 IP+账号 5 次失败 / 5 分钟内即 429
login_limiter = RateLimiter(max_events=5, window_seconds=300)
register_limiter = RateLimiter(max_events=5, window_seconds=300)
