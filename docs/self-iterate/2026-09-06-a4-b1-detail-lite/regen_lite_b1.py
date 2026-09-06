"""A4-B1 R2：装配级再生站点树 lite 模块（rc2_regen 同款模式，非手工 JSON）。

- 行源 = 生产 jobs.json raw 行（8511/10150/10017，审计真源），active 判定沿用现网
  lite 的 job_id 集（与 canonical 生命周期拆分一致）；
- 装配 = build_maintainable_site._lite_payload（与全链构建同一函数）；
- meta 沿用现网 lite meta（total/recruits/examCounts/cities/categories/…），
  仅叠加 B1 三键（source_ref/observed_at/evidence_note）；
- manifest：site-manifest.json 的 jobs_lite 条目 bytes/sha256 由 _write_json
  编码重算，其余字段逐键不动；
- 资产：templates/maintainable-site.js（含 A4-B1 前端）同步至 网站/assets/；
- .gz：随后跑 build_gz.py（幂等，mtime 判定重压）。
排除行（110）不在 lite，详情深链走整包回退（openDetail fallback）。
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

SRC = Path(r'E:\zcode\择岗\项目源码')
SITE = Path(r'E:\zcode\择岗\网站')
sys.path.insert(0, str(SRC))
from tools.anhui_web.build_maintainable_site import (  # noqa: E402
    _lite_payload,
    _major_city_payload,
    _write_json,
)

MANIFEST = SITE / "data" / "site-manifest.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


manifest = load(MANIFEST)
entries = {str(entry.get("cycle")): entry for entry in manifest.get("cycles", [])}

for cycle in ("2024", "2025", "2026"):
    jobs = load(SITE / "data" / "cycles" / cycle / "jobs.json")
    raw_rows = [r for r in jobs["allMajors"]["rows"] if isinstance(r, dict)]
    lite_path = SITE / "data" / "cycles" / cycle / "jobs_lite.json"
    cur = load(lite_path)
    cur_meta = cur.get("allMajors", {}).get("meta", {}) or {}
    active_ids = {str(r.get("job_id")) for r in cur["allMajors"]["rows"]}
    active = [r for r in raw_rows if str(r.get("job_id") or r.get("row_id")) in active_ids]
    job_index = {str(r.get("job_id") or r.get("row_id")): i for i, r in enumerate(raw_rows)}
    pos = load(SITE / "data" / "cycles" / cycle / "positions.json")
    pos_rows = pos.get("rows") or []
    src0 = (pos_rows[0].get("source") or {}) if pos_rows else {}

    payload = _lite_payload(
        cycle,
        active,
        cur_meta,
        job_index=job_index,
        source_info={
            "source_ref": src0.get("source_ref"),
            "observed_at": src0.get("observed_at"),
            "evidence_note": src0.get("note"),
        },
    )
    assert len(payload["allMajors"]["rows"]) == len(cur["allMajors"]["rows"]), f"{cycle} 行数漂移"

    before = lite_path.stat().st_size
    encoded = _write_json(lite_path, payload)
    entry = entries[cycle].setdefault("modules", {}).get("jobs_lite", {})
    entry.update({
        "data": f"data/cycles/{cycle}/jobs_lite.json",
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "schema": payload.get("schema"),
    })
    print(f"{cycle}: lite {before:,} -> {len(encoded):,} bytes | sha {entry['sha256'][:12]}…")

    # major_city 溯源重绑（provenance 绑定 jobs_lite sha256）
    mc_path = SITE / "data" / "cycles" / cycle / "major_city.json"
    mc = _major_city_payload(cycle, active, hashlib.sha256(encoded).hexdigest())
    mc_encoded = _write_json(mc_path, mc)
    mc_entry = entries[cycle].setdefault("modules", {}).get("major_city", {})
    mc_entry.update({
        "data": f"data/cycles/{cycle}/major_city.json",
        "bytes": len(mc_encoded),
        "sha256": hashlib.sha256(mc_encoded).hexdigest(),
        "schema": mc.get("schema"),
    })
    print(f"{cycle}: major_city rebound -> {mc_entry['sha256'][:12]}…")

_write_json(MANIFEST, manifest)
print("manifest patched (jobs_lite ×3)")

asset = SITE / "assets" / "maintainable-site.js"
shutil.copyfile(SRC / "tools" / "anhui_web" / "templates" / "maintainable-site.js", asset)
print(f"asset synced: maintainable-site.js {asset.stat().st_size:,} bytes (模板→站点，模板一致性纪律)")
