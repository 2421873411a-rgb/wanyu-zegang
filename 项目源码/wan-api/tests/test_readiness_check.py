"""readiness_check 单元测试（审计 API-004/API-005 回归锁）。"""
from pathlib import Path

from scripts.readiness_check import compute_ready, migration_ok, static_data_dir


class _FakeSettings:
    def __init__(self, base: Path):
        self.STATIC_DATA_PATH = str(base)


def _seed_real_layout(base: Path, cycles=("2024", "2025", "2026")) -> None:
    for cycle in cycles:
        target = base / "cycles" / cycle
        target.mkdir(parents=True, exist_ok=True)
        (target / "jobs.json").write_text("{}", encoding="utf-8")


def test_static_data_uses_cycles_layout(tmp_path):
    """API-004：必须按 <STATIC_DATA_PATH>/cycles/<cycle>/jobs.json 判定。"""
    _seed_real_layout(tmp_path)
    settings = _FakeSettings(tmp_path)
    assert static_data_dir(settings) == tmp_path / "cycles"
    assert all((tmp_path / "cycles" / c / "jobs.json").is_file() for c in ("2024", "2025", "2026"))


def test_static_data_missing_cycle_reports_false(tmp_path):
    _seed_real_layout(tmp_path, cycles=("2024", "2025"))
    (tmp_path / "cycles" / "2026").mkdir()  # 目录在但没有 jobs.json
    from scripts.readiness_check import check_static_data

    result = check_static_data(_FakeSettings(tmp_path))
    assert result == {"2024": True, "2025": True, "2026": False}


def test_compute_ready_does_not_short_circuit_db_on_optional_redis():
    """API-005 回归：redis 非必需时，DB 不可达必须判 NOT ready（旧表达式会短路成 ready）。"""
    assert compute_ready(db_ok=False, redis_required=False, redis_reachable=False, static_all_ok=True) is False
    assert compute_ready(db_ok=True, redis_required=False, redis_reachable=False, static_all_ok=True) is True
    assert compute_ready(db_ok=True, redis_required=True, redis_reachable=False, static_all_ok=True) is False
    assert compute_ready(db_ok=True, redis_required=True, redis_reachable=True, static_all_ok=True) is True
    assert compute_ready(db_ok=True, redis_required=False, redis_reachable=False, static_all_ok=False) is False


def test_migration_ok_semantics():
    # 评审 P3：恰一行判定，与 init_db 同谓词
    assert migration_ok(["0004"], ["0004"])["ok"] is True
    assert migration_ok(["0003"], ["0004"])["ok"] is False
    # 评审 P2：空表 → False（init_db 生产路径对空表拒启，就绪信号不得相反）
    assert migration_ok([], ["0004"])["ok"] is False
    assert migration_ok(None, ["0004"])["ok"] is False  # 查询失败按不可判处理
    assert migration_ok(["0004", "0003"], ["0004"])["ok"] is False  # 版本表污染（多行）
    assert migration_ok(["0004"], ["0004", "0005"])["ok"] is False  # 多 head 异常
