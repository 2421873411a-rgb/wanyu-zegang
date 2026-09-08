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
    """进程内滑动窗口 + 锁定窗口 + 容量上限。

    check(key) 是原子的"记录+判定"：窗口内事件数已达上限时，置锁定
    （持续一个窗口期，期间拒绝且不追加，保证可恢复性）并返回 False。
    超过 _MAX_KEYS 时按 last_seen（真 LRU）清扫（Round-3 RA-7：distinct key
    永不回收曾是内存 DoS 面——20 万 key ≈150MB 实测；Round-7 终审修正：
    原实现超限时按键名字典序丢弃，会误删活跃攻击 IP 的计数）。
    """

    _MAX_KEYS = 50_000

    def __init__(self, max_events: int, window_seconds: float):
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict = defaultdict(deque)
        self._locked_until: dict = {}
        self._last_seen: dict = {}
        self._lock = Lock()

    def _sweep_if_needed(self, now: float) -> None:
        if len(self._events) <= self._MAX_KEYS and len(self._locked_until) <= self._MAX_KEYS:
            return
        # 第一层：窗口外整键回收（确定性 TTL）
        stale = [k for k, q in self._events.items()
                 if not q or now - q[0] > self.window_seconds]
        for k in stale:
            self._events.pop(k, None)
            self._last_seen.pop(k, None)
        stale_locks = [k for k, until in self._locked_until.items() if now >= until]
        for k in stale_locks:
            self._locked_until.pop(k, None)
        # 第二层（极端攻击仍超限）：按 last_seen 真 LRU 丢弃最旧的一半——
        # 活跃攻击方的计数按其最近活动时间保留，久未访问者先回收
        if len(self._events) > self._MAX_KEYS:
            by_last_seen = sorted(self._events, key=lambda k: self._last_seen.get(k, 0))
            for k in by_last_seen[: len(by_last_seen) // 2]:
                self._events.pop(k, None)
                self._last_seen.pop(k, None)
        if len(self._last_seen) > self._MAX_KEYS * 2:
            for k in sorted(self._last_seen, key=lambda k: self._last_seen[k])[: self._MAX_KEYS]:
                self._last_seen.pop(k, None)

    async def check(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._sweep_if_needed(now)
            self._last_seen[key] = now
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
            self._last_seen.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
            self._locked_until.clear()
            self._last_seen.clear()


_SLIDING_LUA = """
-- 时钟统一取 Redis 侧 TIME（Round-3 RA-6：应用实例时钟漂移会整体绕过窗口）
local t = redis.call('TIME')
local now = t[1] * 1000 + math.floor(t[2] / 1000)
local cut = now - tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, cut)
if redis.call('EXISTS', KEYS[2]) == 1 then return 0 end
local n = redis.call('ZCARD', KEYS[1])
if n >= tonumber(ARGV[3]) then
  redis.call('SET', KEYS[2], '1', 'PX', tonumber(ARGV[2]))
  return 0
end
redis.call('ZADD', KEYS[1], now, now .. ':' .. redis.call('INCR', KEYS[1] .. ':seq'))
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
        # 仅测试环境允许清空（Round-3 RA-9：rl:* 全库 scan 一旦指向共享/生产
        # Redis 会清空全部限流状态）
        if settings.ENV != "test":
            logger.warning("RedisRateLimiter.reset() 在非 test 环境被拒绝执行")
            return
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
# per-IP 总量桶（Round-7 终审加固：(ip,email) 分桶可被换邮箱绕过做撞库/批量注册）
login_ip_limiter = _build("login_ip", 30, 3600)
register_ip_limiter = _build("register_ip", 10, 3600)
refresh_limiter = _build("refresh", settings.REFRESH_MAX_EVENTS, settings.REFRESH_WINDOW_SECONDS)
logout_limiter = _build("logout", settings.LOGOUT_MAX_EVENTS, settings.LOGOUT_WINDOW_SECONDS)
