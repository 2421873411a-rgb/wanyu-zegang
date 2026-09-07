"""限流器（v17.9.12 重建：原子判定 + 可选 Redis 后端）。

v17.9.1 的 allow()/hit() 分离存在 check-then-hit 竞态：allow 与 hit 之间隔着
bcrypt 验证（数百毫秒的 await 窗口），并发请求可全部穿透"5 次/5 分钟"
（Round-2 审计实测 20/20 穿透）。本版统一为**单步原子 check()**：先记录后判定，
宁可错杀不放过。

两个后端：
- MemoryRateLimiter：进程内滑动窗口（含锁定窗口），单 worker 部署的默认；
- RedisRateLimiter：Lua 原子滑动窗 + 锁定键，多 worker 安全；Redis 不可达时
  fail-open 降级到按 worker 数收紧的进程内兜底（登录是核心路径，Redis 抖动
  不应放大成全站拒服务；但纯 fail-open 会退回可击穿状态，故保留兜底）。

key 无界增长问题一并解决：Redis 走 TTL；内存版锁定期内不追加、恢复后自然回收。
"""
import hashlib
import logging
import time
from collections import defaultdict, deque
from threading import Lock

from app.config import settings

logger = logging.getLogger("wanyu.rate_limit")


class MemoryRateLimiter:
    """进程内滑动窗口 + 锁定窗口。

    check(key) 是原子的"记录+判定"：窗口内事件数已达上限时，置锁定
    （持续一个窗口期，期间拒绝且不追加，保证可恢复性）并返回 False。
    """

    def __init__(self, max_events: int, window_seconds: float):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict = defaultdict(deque)
        self._locked_until: dict = {}
        self._lock = Lock()

    async def check(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            locked_until = self._locked_until.get(key)
            if locked_until is not None:
                if now < locked_until:
                    return False
                self._locked_until.pop(key, None)
                self._events.pop(key, None)
            q = self._events[key]
            while q and now - q[0] > self.window_seconds:
                q.popleft()
            if len(q) >= self.max_events:
                self._locked_until[key] = now + self.window_seconds
                self._events.pop(key, None)
                return False
            q.append(now)
            return True

    async def clear(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)
            self._locked_until.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._locked_until.clear()


_SLIDING_LUA = """
local cut = tonumber(ARGV[1]) - tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, cut)
if redis.call('EXISTS', KEYS[2]) == 1 then return 0 end
local n = redis.call('ZCARD', KEYS[1])
if n >= tonumber(ARGV[3]) then
  redis.call('SET', KEYS[2], '1', 'PX', tonumber(ARGV[2]))
  return 0
end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[1] .. ':' .. redis.call('INCR', KEYS[1] .. ':seq'))
redis.call('PEXPIRE', KEYS[1], tonumber(ARGV[2]))
redis.call('PEXPIRE', KEYS[1] .. ':seq', tonumber(ARGV[2]))
return 1
"""


class RedisRateLimiter:
    """Redis 原子滑动窗口（Lua 单次 RTT 完成 清窗+判定+记录/锁定）。

    Redis 不可达 → fail-open 降级到按 RATE_LIMIT_FALLBACK_WORKERS 收紧的
    进程内兜底（防爆破强度不被网络故障清零），并打 ERROR 日志（60s 节流）。
    """

    def __init__(self, scope: str, max_events: int, window_seconds: float):
        self.scope = scope
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._redis = None
        self._script = None
        # 兜底：按多 worker 稀释收紧（单进程内仍是原子的）
        workers = max(1, min(int(settings.RATE_LIMIT_FALLBACK_WORKERS), 4))
        self._fallback = MemoryRateLimiter(max_events=max(1, max_events // workers),
                                           window_seconds=window_seconds)
        self._last_error_log = 0.0

    def _key(self, key: str) -> str:
        digest = hashlib.sha256(f"{self.scope}:{key}".encode("utf-8")).hexdigest()[:24]
        return f"rl:{digest}"

    def _connect(self):
        if self._redis is None:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                settings.REDIS_URL, decode_responses=True,
                socket_connect_timeout=0.5, socket_timeout=0.5,
            )
            self._script = self._redis.register_script(_SLIDING_LUA)
        return self._redis

    def _log_error_throttled(self, exc: Exception) -> None:
        now = time.monotonic()
        if now - self._last_error_log > 60:
            self._last_error_log = now
            logger.error("限流 Redis 后端不可达，降级进程内兜底（scope=%s）：%s", self.scope, exc)

    async def check(self, key: str) -> bool:
        rkey = self._key(key)
        lock_key = rkey + ":lock"
        try:
            redis = self._connect()
            result = await self._script(
                keys=[rkey, lock_key],
                args=[int(time.time() * 1000),
                      int(self.window_seconds * 1000),
                      int(self.max_events)],
            )
            return int(result) == 1
        except Exception as exc:  # Redis 不可达：fail-open + 兜底
            self._log_error_throttled(exc)
            self._redis = None
            self._script = None
            return await self._fallback.check(key)

    async def clear(self, key: str) -> None:
        rkey = self._key(key)
        try:
            redis = self._connect()
            await redis.delete(rkey, rkey + ":lock", rkey + ":seq")
        except Exception as exc:
            self._log_error_throttled(exc)
            self._redis = None
            self._script = None
            await self._fallback.clear(key)

    def reset(self) -> None:
        """测试 fixture 用：确定性清空本 limiter 相关键。

        必须用同步短连接——aioredis 连接绑定创建它的事件循环，而每个测试
        都是新循环，缓存的 async 连接在 fixture 上下文里必然失效（曾导致
        flush 静默失败、限流键跨测试累积、注册全 429）。
        """
        self._fallback.reset()
        self._redis = None
        self._script = None
        try:
            import redis as sync_redis

            client = sync_redis.from_url(
                settings.REDIS_URL, decode_responses=True,
                socket_connect_timeout=1, socket_timeout=1,
            )
            try:
                for k in client.scan_iter(match="rl:*", count=200):
                    client.delete(k)
            finally:
                client.close()
        except Exception:
            pass


def _build(scope: str, max_events: int, window_seconds: float):
    if settings.RATE_LIMIT_BACKEND.strip().lower() == "redis":
        return RedisRateLimiter(scope, max_events, window_seconds)
    return MemoryRateLimiter(max_events, window_seconds)


# 登录/注册/刷新/登出限流：key 维度见调用方（ip+账号 或 ip）
login_limiter = _build("login", settings.LOGIN_MAX_FAILURES, settings.LOGIN_WINDOW_SECONDS)
register_limiter = _build("register", settings.REGISTER_MAX_EVENTS, settings.REGISTER_WINDOW_SECONDS)
refresh_limiter = _build("refresh", settings.REFRESH_MAX_EVENTS, settings.REFRESH_WINDOW_SECONDS)
logout_limiter = _build("logout", settings.LOGOUT_MAX_EVENTS, settings.LOGOUT_WINDOW_SECONDS)
