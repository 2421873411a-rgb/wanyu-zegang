"""门禁场景 4/5：对比列表 ≤4（回归 func NameError）、重复收藏/对比数据库兜底。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.compare_list import CompareList
from app.models.saved_position import SavedPosition

from tests.conftest import get_test_session_factory, _auth, _register

pytestmark = pytest.mark.asyncio

_ROW = {"record_id": "job-2026-test", "cycle": "2026"}


async def test_compare_limit_four_and_func_import_works(client: AsyncClient):
    """门禁5：第 5 个对比岗位必须 400——此路径走 func.count（回归 NameError 修复）。"""
    data = await _register(client)
    headers = _auth(data["access_token"])
    for i in range(4):
        r = await client.post("/api/v1/user/compare", headers=headers,
                              json={"record_id": f"job-cmp-{i}", "cycle": "2026"})
        assert r.status_code == 201, r.text
    fifth = await client.post("/api/v1/user/compare", headers=headers,
                              json={"record_id": "job-cmp-4", "cycle": "2026"})
    assert fifth.status_code == 400
    assert "最多4个" in fifth.json()["detail"]


async def test_compare_duplicate_rejected(client: AsyncClient):
    data = await _register(client)
    headers = _auth(data["access_token"])
    r1 = await client.post("/api/v1/user/compare", headers=headers, json=_ROW)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/user/compare", headers=headers, json=_ROW)
    assert r2.status_code == 400


async def test_compare_unique_constraint_at_db_level(client: AsyncClient):
    """门禁4：绕过应用层直插重复行必须被数据库 UNIQUE 拒绝。"""
    data = await _register(client)
    async with get_test_session_factory()() as session:
        uid = data["user"]["id"]
        session.add(CompareList(user_id=uid, record_id="job-2026-x", cycle="2026"))
        await session.commit()
        session.add(CompareList(user_id=uid, record_id="job-2026-x", cycle="2026"))
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_saved_position_duplicate_rejected(client: AsyncClient):
    data = await _register(client)
    headers = _auth(data["access_token"])
    r1 = await client.post("/api/v1/user/positions", headers=headers, json=_ROW)
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/user/positions", headers=headers, json=_ROW)
    assert r2.status_code == 400
    # 删除后可再收藏
    r3 = await client.delete("/api/v1/user/positions/job-2026-test", headers=headers)
    assert r3.status_code == 204
    r4 = await client.post("/api/v1/user/positions", headers=headers, json=_ROW)
    assert r4.status_code == 201


async def test_saved_position_unique_constraint_at_db_level(client: AsyncClient):
    """门禁4：收藏表数据库层 UNIQUE 兜底。"""
    data = await _register(client)
    async with get_test_session_factory()() as session:
        uid = data["user"]["id"]
        session.add(SavedPosition(user_id=uid, record_id="job-2026-y", cycle="2026"))
        await session.commit()
        session.add(SavedPosition(user_id=uid, record_id="job-2026-y", cycle="2026"))
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_delete_missing_items_404(client: AsyncClient):
    data = await _register(client)
    headers = _auth(data["access_token"])
    r1 = await client.delete("/api/v1/user/positions/ghost", headers=headers)
    assert r1.status_code == 404
    r2 = await client.delete("/api/v1/user/compare/ghost", headers=headers)
    assert r2.status_code == 404
