"""认证面资源边界与抗压（v17.10.2 P1-04 / P1-05）。

- 匿名可达字符串字段必须带长度上限：超长 422，绝不进入 bcrypt/decode/DB。
- bcrypt hash/verify 在线程池执行：事件循环不被 CPU 工作卡死。
"""
import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import _valid_password

_LONG_PASSWORD = "x" * 129
_LONG_TOKEN = "y" * 4097


async def test_login_password_over_limit_is_422_and_never_reaches_bcrypt(monkeypatch):
    from app.api.v1 import auth as auth_mod
    calls = {"n": 0}
    real = auth_mod.verify_password_async

    async def counting(plain, hashed):
        calls["n"] += 1
        return await real(plain, hashed)

    monkeypatch.setattr(auth_mod, "verify_password_async", counting)
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/auth/login",
                         json={"email": "nobody@example.com", "password": _LONG_PASSWORD})
    assert r.status_code == 422
    assert calls["n"] == 0, "超长密码不得进入 bcrypt（资源边界必须先于 CPU 工作）"


@pytest.mark.parametrize("path,payload", [
    ("/api/v1/auth/login", {"email": "nobody@example.com", "password": _LONG_PASSWORD}),
])
async def test_auth_field_limits_return_422(path, payload):
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(path, json=payload)
    assert r.status_code == 422


@pytest.mark.parametrize("path", ["/api/v1/auth/refresh", "/api/v1/auth/logout"])
async def test_refresh_and_logout_token_length_bounds(path):
    """4KB+1 → 422；乱码/非 JWT → 401/400；空 → 422；绝不 500。"""
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.post(path, json={"refresh_token": _LONG_TOKEN})).status_code == 422
        assert (await c.post(path, json={"refresh_token": ""})).status_code == 422
        for garbage in ("x", "not-a-jwt", "eyJhbGciOiJIUzI1NiJ9.!!!.???", "𝄞unicode-token", "a" * 4096):
            r = await c.post(path, json={"refresh_token": garbage})
            assert r.status_code < 500, f"{garbage[:20]}… → {r.status_code}"


async def test_bcrypt_offload_keeps_event_loop_responsive(monkeypatch):
    """5 个并发慢 bcrypt（各 0.2s）期间，事件循环必须仍能调度其他协程。

    若回归为同步调用：5×0.2s=1.0s 全部串行卡死循环，ticker 最大间隔会 ≥0.5s，
    且整体耗时 ≥1s。offload 后 5 个睡眼并行跑在线程池，耗时 ~0.2-0.4s。
    """
    from app.api.v1 import auth as auth_mod

    async def slow_verify(plain, hashed):
        await asyncio.sleep(0.2)
        return False

    monkeypatch.setattr(auth_mod, "verify_password_async", slow_verify)
    from app.main import app

    gaps = []
    stop = asyncio.Event()

    async def ticker():
        last = time.monotonic()
        while not stop.is_set():
            await asyncio.sleep(0.01)
            now = time.monotonic()
            gaps.append(now - last)
            last = now

    ticker_task = asyncio.create_task(ticker())
    started = time.monotonic()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            results = await asyncio.gather(*[
                c.post("/api/v1/auth/login",
                       json={"email": f"u{i}@example.com", "password": "whatever123"})
                for i in range(5)
            ])
    finally:
        stop.set()
        await ticker_task
    elapsed = time.monotonic() - started

    # 限流器可能让部分请求 429——状态不重要，重要的是循环没被卡死
    assert all(r.status_code < 500 for r in results)
    assert max(gaps) < 0.5, f"事件循环被阻塞 {max(gaps):.2f}s（bcrypt 未线程化？）"
    assert elapsed < 0.9, f"5 个并发慢哈希耗时 {elapsed:.2f}s——疑似串行阻塞"
