"""只在 PostgreSQL CI 运行的真实并发门禁。"""
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import _auth, _register, using_postgres

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not using_postgres(), reason="requires PostgreSQL"),
]


async def _new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_same_refresh_token_concurrent_rotation_is_serialized(client: AsyncClient):
    """两个独立请求同时消费同一 refresh：只能一个成功，重用触发 family 撤销。"""
    data = await _register(client, email="race@example.com", username="race")
    old_refresh = data["refresh_token"]

    async def rotate():
        async with await _new_client() as c:
            return await c.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})

    first, second = await asyncio.gather(rotate(), rotate())
    statuses = sorted([first.status_code, second.status_code])
    assert statuses == [200, 401], (first.text, second.text)

    winner = first if first.status_code == 200 else second
    # 失败的并发重用请求按安全策略撤销整个 family，所以胜者刚拿到的新 token 也必须失效。
    replay = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": winner.json()["refresh_token"]},
    )
    assert replay.status_code == 401


async def test_compare_four_slot_limit_holds_under_concurrency(client: AsyncClient):
    """先占 3 槽，再同时争最后 1 槽；最终列表绝不能超过 4。"""
    data = await _register(client, email="slots@example.com", username="slots")
    headers = _auth(data["access_token"])
    for i in range(3):
        r = await client.post(
            "/api/v1/user/compare",
            headers=headers,
            json={"record_id": f"seed-{i}", "cycle": "2026"},
        )
        assert r.status_code == 201, r.text

    async def add(record_id: str):
        async with await _new_client() as c:
            return await c.post(
                "/api/v1/user/compare",
                headers=headers,
                json={"record_id": record_id, "cycle": "2026"},
            )

    r1, r2 = await asyncio.gather(add("race-a"), add("race-b"))
    assert sorted([r1.status_code, r2.status_code]) == [201, 400], (r1.text, r2.text)
    final = await client.get("/api/v1/user/compare", headers=headers)
    assert final.status_code == 200
    assert len(final.json()) == 4
