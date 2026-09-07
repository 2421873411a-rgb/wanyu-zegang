"""Redis 限流后端门禁（仅在 CI 提供 REDIS_URL 时运行；memory 模式默认跳过）。

覆盖 v17.9.12 RedisRateLimiter 的 Lua 原子滑动窗：放行/拒绝/锁定/清窗恢复/降级。
"""
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.utils import rate_limit as rl

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not rl.settings.RATE_LIMIT_BACKEND.strip().lower() == "redis"
                       or not rl.settings.REDIS_URL,
                       reason="requires RATE_LIMIT_BACKEND=redis + REDIS_URL"),
]


async def test_redis_limiter_atomic_window():
    limiter = rl.RedisRateLimiter("ci-test", max_events=3, window_seconds=60)
    results = [await limiter.check("ip:case1") for _ in range(5)]
    assert results == [True, True, True, False, False], results
    await limiter.clear("ip:case1")
    assert await limiter.check("ip:case1") is True


async def test_redis_limiter_isolated_by_key():
    limiter = rl.RedisRateLimiter("ci-test-iso", max_events=1, window_seconds=60)
    a = await limiter.check("ip:alpha")
    b = await limiter.check("ip:alpha")
    c = await limiter.check("ip:beta")
    assert (a, b, c) == (True, False, True)


async def test_end_to_end_login_rate_limit_via_redis():
    """端到端：Redis 后端下第 6 次错密码登录必须 429。"""
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/v1/auth/register", json={
            "email": "redisrl@example.com", "username": "redisrl", "password": "abc1234567"})
        codes = []
        for _ in range(6):
            r = await c.post("/api/v1/auth/login",
                             json={"email": "redisrl@example.com", "password": "wrong-pass-1"})
            codes.append(r.status_code)
    assert codes[:5] == [401] * 5
    assert codes[5] == 429, codes
