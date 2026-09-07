# -*- coding: utf-8 -*-
"""真数据端到端门禁（§10 门8 的 CI 固化，v17.9.11 C2）。

证明三件事：
1. canonical 三周期（all_majors + provenance）与静态派生三周期（allMajors）全部
   通过 fail-closed 快照校验；
2. import_all_data 在临时 SQLite 上全量导入成功，行数/MirrorState/Cycle 口径与
   数据事实基线一致（2024=10017、2025=10150、2026=8511 行/8401 active）；
3. 幂等重跑：第二遍 imported=0 且 deactivated=0（v17.9.11 前复核事件会翻倍）。

任何一步失败进程非零退出。只读仓库内数据，临时库落在系统临时目录。
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

WAN_API_ROOT = Path(__file__).resolve().parents[1]        # wan-api/（app 包所在）
REPO_ROOT = Path(__file__).resolve().parents[3]           # 仓库根
PROJECT_SRC = Path(__file__).resolve().parents[2]         # 项目源码/
sys.path.insert(0, str(WAN_API_ROOT))

CANONICAL_DIR = PROJECT_SRC / "canonical" / "cycles"
STATIC_ROOT = REPO_ROOT / "网站" / "data"
EXPECTED = {
    "2024": {"rows": 10017, "active": 10017},
    "2025": {"rows": 10150, "active": 10150},
    "2026": {"rows": 8511, "active": 8401},
}
EXPECTED_SALARY = 160
EXPECTED_REVIEW = 7


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def stage1_validate_snapshots() -> None:
    from app.services.import_service import validate_snapshot

    for cycle in ("2024", "2025", "2026"):
        errors = validate_snapshot(cycle, _load(CANONICAL_DIR / f"{cycle}.json"))
        assert not errors, (f"canonical {cycle}", errors[:5])
        print(f"[e2e] canonical {cycle}: validate PASS")
        errors = validate_snapshot(cycle, _load(STATIC_ROOT / "cycles" / cycle / "jobs.json"))
        assert not errors, (f"static {cycle}", errors[:5])
        print(f"[e2e] static   {cycle}: validate PASS")


async def stage2_import_and_verify(static_root: Path, db_path: str) -> None:
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.database import Base
    from app.models.cycle import Cycle
    from app.models.job import Job
    from app.models.mirror_state import MirrorState
    from app.services.import_service import import_all_data

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as db:
        results = await import_all_data(db, data_path=str(static_root))
        for cycle, expect in EXPECTED.items():
            rows = (await db.execute(select(func.count(Job.id)).where(Job.cycle == cycle))).scalar()
            active = (await db.execute(
                select(func.count(Job.id)).where(Job.cycle == cycle, Job.record_status == "active")
            )).scalar()
            assert rows == expect["rows"], (cycle, rows)
            assert active == expect["active"], (cycle, active)
            ms = (await db.execute(select(MirrorState).where(MirrorState.cycle == cycle))).scalar_one()
            assert ms.source_rows == expect["rows"], (cycle, ms.source_rows)
            assert ms.active_rows == expect["active"], (cycle, ms.active_rows)
            cyc = (await db.execute(select(Cycle).where(Cycle.cycle == cycle))).scalar_one()
            assert cyc.total_posts == expect["active"], (cycle, cyc.total_posts)
            print(f"[e2e] {cycle}: rows={rows} active={active} mirror+cycle 对账 PASS")
        assert results["salary"]["imported"] == EXPECTED_SALARY, results.get("salary")
        assert results["review_events"]["imported"] == EXPECTED_REVIEW, results.get("review_events")
        print(f"[e2e] salary={EXPECTED_SALARY} review={EXPECTED_REVIEW} PASS")

        # 幂等重跑：jobs 全 updated、0 新增、0 下线；salary/review 不翻倍
        r2 = await import_all_data(db, data_path=str(static_root))
        for cycle in EXPECTED:
            s = r2[f"cycle_{cycle}"]
            assert s["imported"] == 0 and s["deactivated"] == 0, (cycle, s)
        assert r2["review_events"]["imported"] == EXPECTED_REVIEW, r2["review_events"]
        print("[e2e] 幂等重跑 PASS（0 imported / 0 deactivated / review 不翻倍）")

    await engine.dispose()


def main() -> int:
    assert CANONICAL_DIR.is_dir(), f"canonical 缺失：{CANONICAL_DIR}"
    assert (STATIC_ROOT / "cycles").is_dir(), f"静态数据缺失：{STATIC_ROOT}"
    stage1_validate_snapshots()

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        asyncio.run(stage2_import_and_verify(STATIC_ROOT, db_path))
    finally:
        try:
            os.remove(db_path)
        except OSError:
            pass
    print("[e2e] 真数据端到端门禁：PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
