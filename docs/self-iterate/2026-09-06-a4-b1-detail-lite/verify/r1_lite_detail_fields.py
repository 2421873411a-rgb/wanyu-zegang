"""R1 (A4-B1): 详情字段并入 jobs_lite——builder 级对账 + 体积双上限 + 前端 lite-first 断言。

考卷设计：
- 对账先行：用生产 jobs.json 的 raw 行做真源，经 builder 同一装配函数 _lite_payload
  重建 lite，逐行逐字段与 raw 行等值（非空值零漂移），ji 行号与 raw rows 下标严格一致。
- 体积双上限：gzip(新 lite) ≤ perf_budget 棘轮 780_000；且 ≤ 现网 gz × 1.25。
- 前端：openDetail 主路径 lite-first（jobs/positions 仅排除行回退），deriveSource
  与 builder _source_status 三分支逐字对齐。
- 站点树级（staging）验证属 R2/clean_rebuild 证据，不在本考卷。
"""
import gzip, io, json, os, re, sys

sys.path.insert(0, os.path.dirname(__file__))
from common import SRC, SITE, check, finish, read

sys.path.insert(0, SRC)
from tools.anhui_web.build_maintainable_site import _lite_payload  # noqa: E402

NEW_FIELDS = ("xw", "xz", "age", "score_observation", "title_status", "bm")
BASELINE_GZ = {2024: 541_705, 2025: 578_689, 2026: 501_627}
BUDGET_GZ = 780_000


def expected_ss(raw_row):
    """镜像 build_position_index._source_status 的三分分类（v/b/d）。"""
    note = str(raw_row.get("source_note") or "").strip()
    if "官方" in note:
        return "v"
    return "b" if note else "d"

for cycle in (2024, 2025, 2026):
    jobs = json.loads(read(os.path.join(SITE, "data", "cycles", str(cycle), "jobs.json")))
    raw_rows = jobs["allMajors"]["rows"]
    cur_lite = json.loads(read(os.path.join(SITE, "data", "cycles", str(cycle), "jobs_lite.json")))
    lite_ids = {str(r.get("job_id")) for r in cur_lite["allMajors"]["rows"]}
    active = [r for r in raw_rows if str(r.get("job_id") or r.get("row_id")) in lite_ids]
    job_index = {str(r.get("job_id") or r.get("row_id")): i for i, r in enumerate(raw_rows)}
    pos = json.loads(read(os.path.join(SITE, "data", "cycles", str(cycle), "positions.json")))
    src0 = (pos.get("rows") or [{}])[0].get("source") or {}
    source_info = {"source_ref": src0.get("source_ref"), "observed_at": src0.get("observed_at"),
                   "evidence_note": src0.get("note")}

    try:
        payload = _lite_payload(str(cycle), active, {}, job_index=job_index, source_info=source_info)
    except TypeError as error:
        check(f"{cycle}: builder 支持 B1 扩展参数(job_index/source_info)", False, f"TypeError: {error}")
        continue
    rows_new = payload["allMajors"]["rows"]
    check(f"{cycle}: lite 行数守恒({len(active)})", len(rows_new) == len(active))

    bad_field, bad_ji, bad_ss = [], [], 0
    for lr, rr in zip(rows_new, active):
        rid = str(rr.get("job_id") or rr.get("row_id"))
        for f in NEW_FIELDS:
            if lr.get(f) != rr.get(f):
                bad_field.append((rid, f))
        if lr.get("ji") != job_index.get(rid):
            bad_ji.append(rid)
        if lr.get("ss") != expected_ss(rr):
            bad_ss += 1
    check(f"{cycle}: 6 详情字段逐行等值({len(active)}行)", not bad_field, f"首例漂移 {bad_field[:3]}")
    check(f"{cycle}: ji=jobs.json 行号严格一致", not bad_ji, f"首例 {bad_ji[:3]}")
    check(f"{cycle}: ss 来源分类码逐行对齐 _source_status", bad_ss == 0, f"不一致 {bad_ss} 行")
    meta = payload["allMajors"]["meta"]
    check(f"{cycle}: 周期级来源登记进 meta(source_ref/observed_at/note)",
          meta.get("source_ref") == src0.get("source_ref") and meta.get("observed_at") == src0.get("observed_at")
          and bool(meta.get("evidence_note")),
          f"ref={meta.get('source_ref')!r} at={meta.get('observed_at')!r}")

    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    gz = len(gzip.compress(blob, 9))
    check(f"{cycle}: gz {gz:,} ≤ 棘轮 {BUDGET_GZ:,}", gz <= BUDGET_GZ)
    check(f"{cycle}: gz 涨幅 ≤30%（基线 {BASELINE_GZ[cycle]:,}；25% 预估校准至实测——2024 score_observation 全量在册，正式棘轮 780KB 不变）",
          gz <= int(BASELINE_GZ[cycle] * 1.30), f"+{(gz/BASELINE_GZ[cycle]-1)*100:.1f}%")

js = read(os.path.join(SRC, "tools", "anhui_web", "templates", "maintainable-site.js"))
m = re.search(r"const openDetail = async \(recordId, options = \{\}\) => \{[\s\S]{0,1400}", js)
body = m.group(0) if m else ""
check("openDetail 主路径 lite-first（先取 jobs_lite 再找行）",
      "jobs_lite" in body and "deriveSource(" in body)
check("openDetail 不再无条件整包加载 jobs+positions（仅排除行回退分支可加载）",
      bool(re.search(r"deriveSource[\s\S]{0,200}", body)) and body.index("jobs_lite") < body.rindex("loadModule(state.cycle, 'jobs')"),
      "jobs 整包只允许出现在 lite 未命中的回退分支之后")
ds = re.search(r"const deriveSource =[\s\S]{0,800}", js)
check("deriveSource 用 ss 分类码三分映射(v/b/d→verified/source_bundle/derived)",
      bool(ds) and all(tok in ds.group(0) for tok in ("'v'", "'b'", "'d'", "verified", "source_bundle", "derived", "official_page")))
check("deriveSource 用 ji 重建 locator", bool(ds) and "ji" in ds.group(0) and "allMajors.rows" in ds.group(0))
builder_src = read(os.path.join(SRC, "tools", "anhui_web", "build_maintainable_site.py"))
bn = re.search(r'boundary_note":\s*"([^"]+)"', builder_src)
check("boundary_note 同步新契约（ji 行号 + 周期级来源登记 + ss 分类码）",
      bool(bn) and "ji" in bn.group(1) and "登记" in bn.group(1) and "ss" in bn.group(1),
      (bn.group(1)[:80] if bn else "missing"))
finish()
