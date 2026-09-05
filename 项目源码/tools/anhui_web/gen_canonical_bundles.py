# -*- coding: utf-8 -*-
"""v17.8.5-RC3 阶段 E/F：canonical cycle bundle 种子迁移（一次性、可重放校验）。

策略（任务书 G「canonical seed migration」）：legacy_v11（皖域择岗总览.html）经网盘
全库/本机穷尽检索不可恢复，以 7ef107f 的审计生产快照为种子冻结 canonical——
migration_origin = audited_production_snapshot，绝不冒充 raw official source rebuild。

种子输入（全部为审计事实，禁止读取任何派生模块如 lite/catalog/manifest 计数）：
- 网站/data/cycles/{c}/jobs.json 的 allMajors.rows（含 record_status 生命周期的 raw 行）
- 网站/data/cycles/{c}/overview.json 的 cycleInfo/label
- 分数清单文件引用（2026: data/score_lists.json；2024/2025: data/cycles/{c}/score_lists.json）+ sha256
- 审计真源 tools/anhui_web/data/three_year_audit.json（引用，不复制）

产出：
- 项目源码/canonical/cycles/{2024,2025,2026}.json（wanyu-cycle-bundle/v1）
- 事实校验：raw=active+excluded、冻结基线行数、job_id 集合 SHA256、城市维度清点

幂等护栏：canonical 文件已存在时拒绝重写（--force 才允许），防止种子被产物漂移污染。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from tools.anhui_web.build_maintainable_site import _compute_cycle_meta  # noqa: E402
from tools.anhui_web.invariants import BuildInvariantError, require_int  # noqa: E402
from tools.anhui_web.record_lifecycle import split_records  # noqa: E402

PROJECT_ROOT = HERE.parents[1]
WORKSPACE = PROJECT_ROOT.parent
SITE = WORKSPACE / "网站"
CANONICAL_DIR = PROJECT_ROOT / "canonical"
CANONICAL_SCHEMA = "wanyu-cycle-bundle/v1"
BASELINE_COMMIT = "7ef107f"
CANONICAL_CITIES = ("合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山",
                    "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城", "省直")

EXPECTED = {
    "2024": {"raw_posts": 10017, "active_posts": 10017, "excluded_posts": 0, "raw_recruits": 15331, "recruits": 15331},
    "2025": {"raw_posts": 10150, "active_posts": 10150, "excluded_posts": 0, "raw_recruits": 14721, "recruits": 14721},
    "2026": {"raw_posts": 8511, "active_posts": 8401, "excluded_posts": 110, "raw_recruits": 12006, "recruits": 11883},
}
SCORE_LIST_REFS = {
    "2026": "tools/anhui_web/data/score_lists.json",
    "2025": "tools/anhui_web/data/cycles/2025/score_lists.json",
    "2024": "tools/anhui_web/data/cycles/2024/score_lists.json",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def job_id_digest(rows: list[dict]) -> str:
    joined = "\n".join(sorted(str(r.get("job_id") or "") for r in rows))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def build_cycle_doc(cycle: str) -> dict:
    jobs_doc = load_json(SITE / "data" / "cycles" / cycle / "jobs.json")
    overview = load_json(SITE / "data" / "cycles" / cycle / "overview.json")
    prod_meta = jobs_doc["allMajors"].get("meta") or {}
    rows = jobs_doc["allMajors"]["rows"]
    raw_rows, active_rows, excluded_rows = split_records(rows)
    metrics = {
        "raw_posts": len(raw_rows),
        "active_posts": len(active_rows),
        "excluded_posts": len(excluded_rows),
        "raw_recruits": sum(int(r.get("num") or 0) for r in raw_rows),
        "recruits": sum(int(r.get("num") or 0) for r in active_rows),
    }
    for key, expected in EXPECTED[cycle].items():
        if metrics[key] != expected:
            raise BuildInvariantError(f"{cycle}: 种子事实不符 {key}={metrics[key]}（预期 {expected}）——现库已漂移，禁止盲目播种")

    if cycle == "2026":
        # 复原 bundle 原始 meta：行级公式复算 + 非行级字段携带（hire 为构建期投影）
        raw_meta = _compute_cycle_meta(rows)
        for key, value in prod_meta.items():
            if key not in raw_meta:
                raw_meta[key] = json.loads(json.dumps(value, ensure_ascii=False))
        hire = (prod_meta.get("scoreCoverage") or {}).get("hire")
        if hire is not None:
            raw_meta.setdefault("scoreCoverage", {})["hire"] = hire
        meta = raw_meta
    else:
        meta = json.loads(json.dumps(prod_meta, ensure_ascii=False))
        if require_int(meta.get("total"), f"{cycle} meta.total") != metrics["raw_posts"]:
            raise BuildInvariantError(f"{cycle}: jobs meta.total != raw rows")

    score_ref = SCORE_LIST_REFS[cycle]
    score_path = PROJECT_ROOT / score_ref
    score_doc = load_json(score_path)
    keyed_unresolved = (score_doc.get("keyed") or {}).get("unresolved")
    if not isinstance(keyed_unresolved, list):
        raise BuildInvariantError(f"{cycle}: score_lists keyed.unresolved 必须是列表（fail-closed，got {type(keyed_unresolved).__name__}）")
    if keyed_unresolved:
        raise BuildInvariantError(f"{cycle}: keyed.unresolved 非空（{len(keyed_unresolved)} 项），与 resolved=116 事实矛盾，拒绝播种")

    # 城市维度清点：canonical city 之外的原值进 provenance（审计保留）
    raw_city_values = sorted({str(r.get("city") or r.get("reg") or "") for r in rows if str(r.get("city") or r.get("reg") or "")})
    off_dimension = [c for c in raw_city_values if not any(c == k or c.startswith(k) for k in CANONICAL_CITIES if k != "省直") and c != "省直"]

    doc = {
        "schema": CANONICAL_SCHEMA,
        "cycle": cycle,
        "label": str(overview.get("label") or jobs_doc.get("label") or cycle),
        "migration_origin": "audited_production_snapshot",
        "seeded_on": "2026-09-05",
        "seed_baseline_commit": BASELINE_COMMIT,
        "cycle_info": overview.get("cycleInfo") or {},
        "all_majors": {"meta": meta, "rows": rows},
        "score_state": {
            "mode": "reference",
            "file": score_ref,
            "sha256": sha256_file(score_path),
            "cycle": score_doc.get("cycle"),
        },
        "audit_ref": {
            "file": "tools/anhui_web/data/three_year_audit.json",
            "cycle_entry": cycle,
        },
        "metrics": metrics,
        "city_dimension": {
            "canonical_cities": list(CANONICAL_CITIES),
            "user_scope": "city（16市+省直，行内已归一化）",
            "audit_scope": "source_city（历史原值，逐步回填；本种子未回填=null）",
            "off_dimension_source_values": off_dimension,
        },
        "provenance": {
            "seed_inputs": [
                {"path": f"网站/data/cycles/{cycle}/jobs.json", "role": "audited raw rows (allMajors.rows)",
                 "sha256": sha256_file(SITE / "data" / "cycles" / cycle / "jobs.json")},
                {"path": f"网站/data/cycles/{cycle}/overview.json", "role": "cycleInfo/label",
                 "sha256": sha256_file(SITE / "data" / "cycles" / cycle / "overview.json")},
                {"path": score_ref, "role": "score lists reference", "sha256": sha256_file(score_path)},
            ],
            "job_id_set_sha256": job_id_digest(rows),
            "recovery_attempted": "百度网盘全库（无 *总览* 文件）/本机工作区/工作区归档（无 legacy_v11、无历史压缩包）——2026-09-05 穷尽检索不可恢复",
            "verified_facts": [
                "RC2 verifier 294/0（raw=active+excluded、生命周期证据、unresolved 全投影）",
                "record_status_overrides.json 110 组（source_note 疑似重复收录 × D2 交叉核对）",
                "keyed.resolution_20260905 attributed=116 / still_ambiguous=0",
                "three_year_audit.json cycles[cycle] 与冻结基线 10017/10150/8511",
            ],
            "unverifiable_without_legacy": [
                "legacy 单文件 v12 页面模板内容（page_content）——单文件重建引擎列入 v17.9",
                "从 source_data 零成本重放跨会话累积修正（哨兵 629 复活、city_norm、D2 打标的历史路径）",
            ],
        },
    }
    return doc


def main() -> int:
    force = "--force" in sys.argv
    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    (CANONICAL_DIR / "cycles").mkdir(parents=True, exist_ok=True)
    for cycle in ("2024", "2025", "2026"):
        out = CANONICAL_DIR / "cycles" / f"{cycle}.json"
        if out.is_file() and not force:
            print(f"{out.name} 已存在（--force 才允许重播种；防止产物漂移污染真源）")
            continue
        doc = build_cycle_doc(cycle)
        encoded = (json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        out.write_bytes(encoded)
        m = doc["metrics"]
        print(f"{out.name}: raw {m['raw_posts']} = active {m['active_posts']} + excluded {m['excluded_posts']} | "
              f"recruits {m['recruits']}/{m['raw_recruits']} | rows sha {doc['provenance']['job_id_set_sha256'][:12]} | bytes {len(encoded)}")
    print("canonical 种子迁移完成；迁移证明 → docs/migrations/canonical-seed-20260905.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
