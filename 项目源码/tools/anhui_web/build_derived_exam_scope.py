"""P0-9②: 三年趋势 exam_scope 预聚合 —— 消除考试筛选下的全量 jobs.json(34.4MB) 运行时加载。

独立可运行：python build_derived_exam_scope.py [网站根目录]
  - 读取每个周期 网站/data/cycles/{year}/jobs.json，只取 active 行（record_status 为空或 active）；
  - 按考试类别（省考/国考/事业编）聚合岗位数与招录人数（镜像 examRowMatches 的 includes 语义）；
  - 按 exam+城市 二级聚合（城市键镜像 trendCityKey；另计 examinees 供竞争热力图）；
  - 事业编额外按行内 cycle（上半年/下半年联考）细分，供 examSub 筛选；
  - 对每个带 changes.json 的周期，按 (目标周期 derived.json) 写入 change_scope：
    候选行（target 记录优先，缺失回退 base 记录）按考试桶计新增/撤回/修订/保持/待复核，
    镜像 maintainable-site.js changeSummaryForScope；
  - 结果写回各周期 derived.json 的 exam_scope 字段，并同步重建 derived.json.gz。

语义对齐（与 网站/assets/maintainable-site.js 一一对应，保证渲染数字不变）：
  isActiveRow / examRowMatches / trendCityKey / mapCityFor /
  recruits = Number(row.num ?? row.recruits ?? 0) || 0 /
  examinees = Number(row.competition_observations?.examinees?.value ?? row.bm ?? 0)
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path

EXAM_BUCKETS = ("省考", "国考", "事业编")
PREFECTURES = ["合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城"]
STATUS_KEYS = ("added", "withdrawn", "revised", "unchanged", "needs_review")
SUB_KEYS = ("上半年", "下半年")


def js_number(value) -> float:
    """镜像 JS Number()：数字直取；数值字符串转换；其余（含 None 已在上游兜底）按 0。"""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return float("nan")
    return 0.0


def is_active_row(row: dict) -> bool:
    status = row.get("record_status")
    return not status or status == "active"


def record_id_of(row: dict) -> str:
    """镜像 String(row.job_id || row.row_id || row.code || '')。"""
    for key in ("job_id", "row_id", "code"):
        value = row.get(key)
        if value:  # JS || 只跳过假值
            return str(value)
    return ""


def recruits_of(row: dict) -> float:
    value = row.get("num")
    if value is None:
        value = row.get("recruits")
    if value is None:
        value = 0
    number = js_number(value)
    return 0.0 if number != number else number  # NaN -> 0（镜像 ... || 0）


def examinees_of(row: dict) -> float:
    observations = row.get("competition_observations")
    value = None
    if isinstance(observations, dict):
        examinees = observations.get("examinees")
        if isinstance(examinees, dict):
            value = examinees.get("value")
    if value is None:
        value = row.get("bm")
    if value is None:
        value = 0
    number = js_number(value)
    return 0.0 if number != number else number


def map_city_for(value) -> str | None:
    """镜像 mapCityFor：省直/空 -> None；宿松->安庆；广德->宣城；十六市前缀归并。"""
    city = str(value or "").strip()
    if not city or city == "省直":
        return None
    if city == "宿松":
        return "安庆"
    if city == "广德":
        return "宣城"
    for candidate in PREFECTURES:
        if city == candidate or city.startswith(candidate):
            return candidate
    return None


def trend_city_key(value) -> str:
    """镜像 trendCityKey：省直单独保留；未归并值原样保留；空 -> 未标注。"""
    city = str(value or "").strip()
    if city == "省直":
        return "省直"
    return map_city_for(city) or city or "未标注"


def exam_bucket_keys(row: dict) -> list[str]:
    """镜像 examRowMatches 的 includes 语义：一行可命中的考试桶。"""
    value = str(row.get("exam") or "")
    buckets = []
    if "省考" in value:
        buckets.append("省考")
    if "国考" in value:
        buckets.append("国考")
    if "事业" in value:
        buckets.append("事业编")
    return buckets


def row_sub(row: dict) -> str:
    """事业编联考细分键：镜像 String(row.cycle || '')。"""
    return str(row.get("cycle") or "")


def new_city_stats(with_examinees: bool) -> dict:
    stats = {"jobs": 0, "recruits": 0.0}
    if with_examinees:
        stats["examinees"] = 0.0
    stats["subs"] = {}
    return stats


def add_city(stats: dict, recruits: float, examinees: float, sub: str) -> None:
    stats["jobs"] += 1
    stats["recruits"] += recruits
    if "examinees" in stats:
        stats["examinees"] += examinees
    if sub:
        bucket = stats["subs"].get(sub)
        if bucket is None:
            bucket = stats["subs"][sub] = {"jobs": 0, "recruits": 0.0}
            if "examinees" in stats:
                bucket["examinees"] = 0.0
        bucket["jobs"] += 1
        bucket["recruits"] += recruits
        if "examinees" in bucket:
            bucket["examinees"] += examinees


def compact_city(stats: dict, with_subs: bool) -> dict:
    out = OrderedDict()
    out["jobs"] = int(stats["jobs"])
    out["recruits"] = int(stats["recruits"]) if float(stats["recruits"]).is_integer() else round(stats["recruits"], 2)
    if "examinees" in stats:
        examinees = stats["examinees"]
        if examinees:  # 0 时省略键，JS 侧 Number(... || 0) 语义等价
            out["examinees"] = int(examinees) if float(examinees).is_integer() else round(examinees, 2)
    if with_subs and stats["subs"]:
        subs = OrderedDict()
        for sub in SUB_KEYS:
            bucket = stats["subs"].get(sub)
            if not bucket or bucket["jobs"] < 1:
                continue
            entry = OrderedDict()
            entry["jobs"] = int(bucket["jobs"])
            entry["recruits"] = int(bucket["recruits"]) if float(bucket["recruits"]).is_integer() else round(bucket["recruits"], 2)
            if "examinees" in bucket:
                examinees = bucket["examinees"]
                if examinees:
                    entry["examinees"] = int(examinees) if float(examinees).is_integer() else round(examinees, 2)
            subs[sub] = entry
        if subs:
            out["subs"] = subs
    return out


def build_city_buckets(rows: list[dict], with_examinees: bool) -> dict:
    """按考试桶 × 城市聚合；with_examinees 时另计报名人数（v17-tools 竞争热力图用）。"""
    by_city = {exam: {} for exam in EXAM_BUCKETS}
    for row in rows:
        recruits = recruits_of(row)
        examinees = examinees_of(row)
        city = trend_city_key(row.get("city") if str(row.get("city") or "").strip() else row.get("reg"))
        for exam in exam_bucket_keys(row):
            stats = by_city[exam].get(city)
            if stats is None:
                stats = by_city[exam][city] = new_city_stats(with_examinees)
            add_city(stats, recruits, examinees, row_sub(row) if exam == "事业编" else "")
    return by_city


def build_exam_scope(cycle: str, active_rows: list[dict], all_rows: list[dict]) -> tuple[dict, dict]:
    """聚合 by_exam / by_exam_city / by_exam_city_raw；返回 (exam_scope, 调试统计)。

    - by_exam / by_exam_city：active 行口径（主站三年概况表、slopeGraph 趋势，镜像 rowsFor）。
    - by_exam_city_raw：全部行口径（含 record_status=duplicate 的跨市重复收录行）。
      v17-tools.js 竞争热力图/城市对比历史上不按 record_status 过滤，为保证渲染数字
      逐字节不变，工具页消费 raw 桶；examinees 仅供工具使用，故只存在于 raw 桶。
    """
    by_exam = OrderedDict((exam, {"jobs": 0, "recruits": 0.0}) for exam in EXAM_BUCKETS)
    for row in active_rows:
        recruits = recruits_of(row)
        for exam in exam_bucket_keys(row):
            by_exam[exam]["jobs"] += 1
            by_exam[exam]["recruits"] += recruits
    by_city_active = build_city_buckets(active_rows, with_examinees=False)
    by_city_raw = build_city_buckets(all_rows, with_examinees=True)
    multi_bucket = sum(1 for row in active_rows if len(exam_bucket_keys(row)) > 1)

    scope = OrderedDict()
    scope["schema"] = "wanyu-exam-scope/v1"
    by_exam_out = OrderedDict()
    for exam in EXAM_BUCKETS:
        totals = by_exam[exam]
        entry = OrderedDict()
        entry["jobs"] = int(totals["jobs"])
        entry["recruits"] = int(totals["recruits"]) if float(totals["recruits"]).is_integer() else round(totals["recruits"], 2)
        if exam == "事业编":
            subs = OrderedDict()
            for sub in SUB_KEYS:
                sub_jobs = sum(s["subs"].get(sub, {}).get("jobs", 0) for s in by_city_active["事业编"].values())
                sub_recruits = sum(s["subs"].get(sub, {}).get("recruits", 0.0) for s in by_city_active["事业编"].values())
                if sub_jobs < 1:
                    continue
                subs[sub] = OrderedDict([
                    ("jobs", int(sub_jobs)),
                    ("recruits", int(sub_recruits) if float(sub_recruits).is_integer() else round(sub_recruits, 2)),
                ])
            if subs:
                entry["subs"] = subs
        by_exam_out[exam] = entry
    scope["by_exam"] = by_exam_out

    def emit_city_map(by_city: dict, with_subs: bool) -> OrderedDict:
        cities = OrderedDict()
        for exam in EXAM_BUCKETS:
            exam_cities = OrderedDict()
            for city in sorted(by_city[exam], key=lambda c: (-by_city[exam][c]["jobs"], c)):
                if by_city[exam][city]["jobs"] < 1:
                    continue
                exam_cities[city] = compact_city(by_city[exam][city], with_subs=with_subs)
            cities[exam] = exam_cities
        return cities

    scope["by_exam_city"] = emit_city_map(by_city_active, with_subs=True)
    scope["by_exam_city_raw"] = emit_city_map(by_city_raw, with_subs=True)
    debug = {"multi_bucket": multi_bucket, "raw_extra": len(all_rows) - len(active_rows), "unmapped_cities": sorted(c for c in by_city_raw["省考"] if map_city_for(c) is None and c != "省直")}
    return scope, debug


def empty_summary() -> dict:
    return OrderedDict((key, 0) for key in STATUS_KEYS)


def build_change_scope(changes_payload: dict, target_rows: dict, base_rows: dict) -> dict:
    """镜像 changeSummaryForScope：候选行 = target 记录 || base 记录，按考试桶计状态。"""
    buckets = {
        "省考": empty_summary(),
        "国考": empty_summary(),
        "事业编": OrderedDict([("all", empty_summary()), ("上半年", None), ("下半年", None)]),
    }
    missing = 0
    for change in changes_payload.get("changes") or []:
        candidate = target_rows.get(str(change.get("target_record_id") or "")) or base_rows.get(str(change.get("base_record_id") or ""))
        if not candidate:
            missing += 1
            continue
        status = str(change.get("status") or "needs_review")
        if status not in STATUS_KEYS:
            status = "needs_review"
        exam_value = str(candidate.get("exam") or "")
        targets = []
        if "省考" in exam_value:
            targets.append(buckets["省考"])
        if "国考" in exam_value:
            targets.append(buckets["国考"])
        if "事业" in exam_value:
            targets.append(buckets["事业编"]["all"])
            sub = row_sub(candidate)
            if sub in SUB_KEYS:
                if buckets["事业编"][sub] is None:
                    buckets["事业编"][sub] = empty_summary()
                targets.append(buckets["事业编"][sub])
        for target in targets:
            target[status] += 1
    scope = OrderedDict()
    scope["省考"] = buckets["省考"]
    scope["国考"] = buckets["国考"]
    syb = OrderedDict()
    syb["all"] = buckets["事业编"]["all"]
    for sub in SUB_KEYS:
        if buckets["事业编"][sub] is not None:
            syb[sub] = buckets["事业编"][sub]
    scope["事业编"] = syb
    return scope, missing


def write_gz(path: Path) -> None:
    gz = path.with_name(path.name + ".gz")
    tmp = gz.with_suffix(gz.suffix + ".tmp")
    with open(tmp, "wb") as f:
        with gzip.GzipFile(fileobj=f, mode="wb", compresslevel=9, mtime=int(path.stat().st_mtime)) as g:
            g.write(path.read_bytes())
    os.replace(tmp, gz)


def main() -> int:
    site = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[3] / "网站"
    cycles_dir = site / "data" / "cycles"
    if not cycles_dir.is_dir():
        print(f"[错误] 未找到周期数据目录：{cycles_dir}")
        return 1
    cycle_names = sorted(p.name for p in cycles_dir.iterdir() if p.is_dir())
    # 先加载全部周期 jobs 行与记录索引（change_scope 需要相邻周期）
    active_rows: dict[str, list[dict]] = {}
    all_rows: dict[str, list[dict]] = {}
    row_index: dict[str, dict[str, dict]] = {}
    for name in cycle_names:
        jobs_path = cycles_dir / name / "jobs.json"
        if not jobs_path.exists():
            print(f"[警告] {name} 缺少 jobs.json，跳过该周期")
            continue
        with open(jobs_path, encoding="utf-8") as f:
            rows = json.load(f)["allMajors"]["rows"]
        all_rows[name] = rows
        active = [row for row in rows if is_active_row(row)]
        active_rows[name] = active
        row_index[name] = {record_id_of(row): row for row in active if record_id_of(row)}

    total_saved_rows = 0
    for name in cycle_names:
        active = active_rows.get(name)
        if active is None:
            continue
        derived_path = cycles_dir / name / "derived.json"
        if not derived_path.exists():
            print(f"[警告] {name} 缺少 derived.json，跳过 exam_scope 写入")
            continue
        before_size = derived_path.stat().st_size
        with open(derived_path, encoding="utf-8") as f:
            derived = json.load(f)

        scope, debug = build_exam_scope(name, active, all_rows[name])
        if debug["multi_bucket"]:
            print(f"[警告] {name} 有 {debug['multi_bucket']} 行 exam 值同时命中多个考试桶，聚合按桶分别计入")
        if debug["unmapped_cities"]:
            print(f"[提示] {name} 存在未归并十六市的城市值（按原文保留，不参与工具页地图口径）：{debug['unmapped_cities']}")
        if debug["raw_extra"]:
            print(f"[提示] {name} 含 {debug['raw_extra']} 行非 active 记录，已计入 by_exam_city_raw（v17-tools 旧行为口径）")

        # change_scope：本周期 changes.json（base_cycle 的记录索引回退）
        changes_path = cycles_dir / name / "changes.json"
        if changes_path.exists():
            with open(changes_path, encoding="utf-8") as f:
                changes_payload = json.load(f)
            base_cycle = str(changes_payload.get("base_cycle") or "")
            if base_cycle and base_cycle in row_index:
                change_scope, missing = build_change_scope(changes_payload, row_index.get(name, {}), row_index[base_cycle])
                if missing:
                    print(f"[提示] {name} changes.json 有 {missing} 条记录在两个周期岗位行中都找不到（与页面行为一致：不计入）")
                scope["change_scope"] = OrderedDict([(base_cycle, change_scope)])
            else:
                print(f"[提示] {name} changes.json 的 base_cycle={base_cycle or '缺失'} 无岗位数据，跳过 change_scope")

        # 自校验：by_exam 合计 == active 行数 / 招录合计
        assert sum(v["jobs"] for v in scope["by_exam"].values()) == len(active), f"{name} 岗位数合计不符"
        assert sum(v["recruits"] for v in scope["by_exam"].values()) == sum(recruits_of(row) for row in active), f"{name} 招录合计不符"

        derived["exam_scope"] = scope
        with open(derived_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(derived, ensure_ascii=False, separators=(",", ":")) + "\n")
        write_gz(derived_path)
        after_size = derived_path.stat().st_size
        print(f"\n== {name} ==", f"active 行 {len(active)}，derived.json {before_size}B -> {after_size}B")
        for exam in EXAM_BUCKETS:
            entry = scope["by_exam"].get(exam)
            sub_note = ""
            if entry and entry.get("subs"):
                sub_note = "（细分 " + " / ".join(f"{k}:{v['jobs']}岗{v['recruits']}人" for k, v in entry["subs"].items()) + "）"
            print(f"  {exam}: {entry['jobs']} 岗 / {entry['recruits']} 人{sub_note}")
        if scope.get("change_scope"):
            for base_cycle, buckets in scope["change_scope"].items():
                parts = []
                for exam in ("省考", "国考"):
                    total = sum(buckets[exam].values())
                    parts.append(f"{exam}:{total}")
                syb = buckets["事业编"]
                parts.append(f"事业编:{sum(syb['all'].values())}")
                print(f"  change_scope[{base_cycle}] 候选行分桶（全部状态合计）: " + "，".join(parts))
        total_saved_rows += len(active)

    print(f"\n完成：{len(active_rows)} 个周期，共 {total_saved_rows} 行 active 岗位完成预聚合。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
