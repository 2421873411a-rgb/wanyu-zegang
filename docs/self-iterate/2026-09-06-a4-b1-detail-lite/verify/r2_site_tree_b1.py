"""R2 (A4-B1): 站点树再生后校验——lite 字段对账、manifest 哈希链、gz 同步、模板一致性。"""
import gzip, hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(__file__))
from common import SITE, SRC, check, finish, read

FIELDS = ("xw", "xz", "age", "score_observation", "title_status", "bm")
COUNTS = {"2024": 10017, "2025": 10150, "2026": 8401}
BUDGET_GZ = 780_000


def expected_ss(raw_row):
    note = str(raw_row.get("source_note") or "").strip()
    if "官方" in note:
        return "v"
    return "b" if note else "d"


manifest = json.loads(read(os.path.join(SITE, "data", "site-manifest.json")))
entries = {str(e.get("cycle")): e for e in manifest.get("cycles", [])}

for cycle, active_n in COUNTS.items():
    raw_rows = json.loads(read(os.path.join(SITE, "data", "cycles", cycle, "jobs.json")))["allMajors"]["rows"]
    lite_bytes = read(os.path.join(SITE, "data", "cycles", cycle, "jobs_lite.json"), binary=True)
    lite = json.loads(lite_bytes)
    rows = lite["allMajors"]["rows"]
    raw_by_id = {str(r.get("job_id") or r.get("row_id")): (i, r) for i, r in enumerate(raw_rows)}
    check(f"{cycle}: lite 行数={active_n}", len(rows) == active_n, str(len(rows)))

    bad = bad_ji = bad_ss = 0
    for lr in rows:
        rid = str(lr.get("job_id"))
        i, rr = raw_by_id.get(rid, (None, {}))
        if not rr:
            bad += 1
            continue
        if any(lr.get(f) != rr.get(f) for f in FIELDS):
            bad += 1
        if lr.get("ji") != i:
            bad_ji += 1
        if lr.get("ss") != expected_ss(rr):
            bad_ss += 1
    check(f"{cycle}: 6 字段全量对账零漂移", bad == 0, f"{bad} 行异常")
    check(f"{cycle}: ji/ss 全量对齐", bad_ji == 0 and bad_ss == 0, f"ji {bad_ji} / ss {bad_ss}")
    meta = lite["allMajors"]["meta"]
    pos_src0 = (json.loads(read(os.path.join(SITE, "data", "cycles", cycle, "positions.json"))).get("rows") or [{}])[0].get("source") or {}
    check(f"{cycle}: meta 周期级来源登记在册（observed_at 未公布则缺席=站规）",
          "source_ref" in meta and "evidence_note" in meta
          and meta.get("source_ref") == pos_src0.get("source_ref")
          and meta.get("observed_at") == pos_src0.get("observed_at"),
          f"ref={str(meta.get('source_ref'))[:40]} at={meta.get('observed_at')}")

    entry = entries[cycle]["modules"]["jobs_lite"]
    check(f"{cycle}: manifest 哈希链一致", entry["sha256"] == hashlib.sha256(lite_bytes).hexdigest()
          and entry["bytes"] == len(lite_bytes))
    gz_path = os.path.join(SITE, "data", "cycles", cycle, "jobs_lite.json.gz")
    gz_bytes = read(gz_path, binary=True)
    check(f"{cycle}: .gz 同步（解压==源文件）", gzip.decompress(gz_bytes) == lite_bytes)
    check(f"{cycle}: gz {len(gz_bytes):,} ≤ 棘轮 {BUDGET_GZ:,}", len(gz_bytes) <= BUDGET_GZ)

tpl = read(os.path.join(SRC, "tools", "anhui_web", "templates", "maintainable-site.js"), binary=True)
asset = read(os.path.join(SITE, "assets", "maintainable-site.js"), binary=True)
check("模板一致性：网站/assets/maintainable-site.js == templates（13 文件纪律成员）", tpl == asset)
asset_gz = gzip.decompress(read(os.path.join(SITE, "assets", "maintainable-site.js.gz"), binary=True))
check("asset .gz 同步（解压==模板）", asset_gz == tpl)
check("B1 前端已在站点资产中（deriveSource + lite-first）",
      b"deriveSource" in asset and asset.index(b"jobs_lite") < asset.rindex(b"loadModule(state.cycle, 'jobs')"))
finish()
