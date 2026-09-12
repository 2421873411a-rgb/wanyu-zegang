"""只在 PostgreSQL CI 运行的真实并发门禁。"""
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import _auth, _register, _seed_jobs, using_postgres

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
    # v17.9.11 B3：引用必须是真实 active 岗位——先播种 5 个，占 3 争 2
    job_ids = await _seed_jobs(5)
    for jid in job_ids[:3]:
        r = await client.post(
            "/api/v1/user/compare",
            headers=headers,
            json={"record_id": jid, "cycle": "2026"},
        )
        assert r.status_code == 201, r.text

    async def add(record_id: str):
        async with await _new_client() as c:
            return await c.post(
                "/api/v1/user/compare",
                headers=headers,
                json={"record_id": record_id, "cycle": "2026"},
            )

    r1, r2 = await asyncio.gather(add(job_ids[3]), add(job_ids[4]))
    assert sorted([r1.status_code, r2.status_code]) == [201, 400], (r1.text, r2.text)
    final = await client.get("/api/v1/user/compare", headers=headers)
    assert final.status_code == 200
    assert len(final.json()) == 4


async def test_compare_different_positions_hitting_same_slot_both_succeed(client: AsyncClient):
    """v17.10.2 P2-09：并发不同岗位撞同一空闲槽位——重试后两个都成功，不再误报「已存在」。"""
    data = await _register(client, email="slotrace@example.com", username="slotrace")
    headers = _auth(data["access_token"])
    job_ids = await _seed_jobs(4)  # 空列表：4 个空槽，两个并发各加一个不同岗位

    async def add(record_id: str):
        async with await _new_client() as c:
            return await c.post(
                "/api/v1/user/compare",
                headers=headers,
                json={"record_id": record_id, "cycle": "2026"},
            )

    r1, r2 = await asyncio.gather(add(job_ids[0]), add(job_ids[1]))
    assert r1.status_code == 201 and r2.status_code == 201, (r1.text, r2.text)
    final = await client.get("/api/v1/user/compare", headers=headers)
    assert len(final.json()) == 2


async def test_filter_snapshot_quota_holds_under_concurrency(client: AsyncClient):
    """v17.10.2 P2-08：49 份存量 + 10 并发创建——最终必须恰好 50，绝不能 51+。"""
    from sqlalchemy import func, select

    from app.models.filter_snapshot import FilterSnapshot
    from tests.conftest import get_test_session_factory

    data = await _register(client, email="quota@example.com", username="quota")
    headers = _auth(data["access_token"])

    async with get_test_session_factory()() as session:
        for i in range(49):
            session.add(FilterSnapshot(
                user_id=data["user"]["id"], cycle="2026", view="table",
                filters="{}", metric="jobs", release="test",
            ))
        await session.commit()

    async def create(i: int):
        async with await _new_client() as c:
            return await c.post(
                "/api/v1/user/snapshots",
                headers=headers,
                json={"cycle": "2026", "view": "table", "filters": {"kw": str(i)}, "metric": "jobs"},
            )

    results = await asyncio.gather(*[create(i) for i in range(10)])
    ok = sum(1 for r in results if r.status_code == 201)
    rejected = sum(1 for r in results if r.status_code == 400)
    assert (ok, rejected) == (1, 9), [r.status_code for r in results]

    async with get_test_session_factory()() as session:
        total = (await session.execute(
            select(func.count(FilterSnapshot.id)).where(
                FilterSnapshot.user_id == data["user"]["id"])
        )).scalar_one()
    assert total == 50, f"配额被并发击穿：{total}"
