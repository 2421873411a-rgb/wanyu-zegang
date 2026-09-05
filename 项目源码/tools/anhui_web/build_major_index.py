# -*- coding: utf-8 -*-
"""T1 专业智能匹配引擎 · 数据侧：构建专业倒排索引 major-index.json。

匹配口径（推导亮明依据，绝不臆测）：
- zy 原文按分隔符切分（、，,；;／/＋+ 空格），剥「本科：/研究生：/大专：」前缀与专业代码
- token 命中目录成员 → explicit（该专业的考生明确可报）
- token 为目录「XX类」 → by_class（该类全部成员专业的考生可报，依据=该岗要求『XX类』）
- token 含「不限」 → unlimited
- 其余 → unclassified_tokens（宁缺勿错，绝不强行归类）
匹配依据原文由前端从 jobs_lite.zy 现取（索引不冗余存原文）。
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parents[2] / "网站"
SPLIT_RE = re.compile(r"[、，,；;／/＋+\s（）()：:．·\-—]+")
CODE_RE = re.compile(r"^\d{5,6}[A-Za-z]?")
UNLIM_RE = re.compile(r"(不限|无专业限制|专业不限|不受专业限制)")
TAIL_RE = re.compile(r"(等专业|相关专业|专业|类别|等)+$")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_token(token: str) -> str:
    text = CODE_RE.sub("", token.strip()).strip()
    prev = None
    while prev != text and text:
        prev = text
        text = TAIL_RE.sub("", text)
    return text


def parse_zy(zy: str) -> tuple[list[str], bool]:
    """返回（归一 token 列表, 是否专业不限）。"""
    text = str(zy or "").strip()
    if not text:
        return [], False
    for prefix in ("本科：", "研究生：", "大专：", "本科:", "研究生:", "大专:"):
        text = text.replace(prefix, "、")
    tokens = []
    unlim = False
    for raw in SPLIT_RE.split(text):
        token = clean_token(raw)
        if not token:
            continue
        if UNLIM_RE.search(token):
            unlim = True
            continue
        tokens.append(token)
    return tokens, unlim


def build(catalog_map: dict, rows: list) -> dict:
    member_classes: dict[str, list[str]] = {}
    for major, classes in catalog_map.items():
        names = classes if isinstance(classes, list) else [classes]
        member_classes[str(major).strip()] = [str(c).strip() for c in names]
    class_members: dict[str, list[str]] = collections.defaultdict(list)
    for major, classes in member_classes.items():
        for cl in classes:
            class_members[cl].append(major)
    lowered_members = {name.lower(): name for name in member_classes}
    lowered_classes = {name.lower(): name for name in class_members}

    explicit: dict[str, list[str]] = collections.defaultdict(list)
    by_class: dict[str, list[str]] = collections.defaultdict(list)
    unlimited: list[str] = []
    unclassified: collections.Counter = collections.Counter()
    explicit_count: collections.Counter = collections.Counter()
    class_count: collections.Counter = collections.Counter()

    for row in rows:
        job_id = str(row.get("job_id") or row.get("code") or "")
        tokens, unlim = parse_zy(row.get("zy"))
        if unlim:
            unlimited.append(job_id)
        for token in tokens:
            low = token.lower()
            if low in lowered_members:
                name = lowered_members[low]
                explicit[name].append(job_id)
                explicit_count[name] += 1
            elif low in lowered_classes:
                name = lowered_classes[low]
                by_class[name].append(job_id)
                class_count[name] += 1
            else:
                unclassified[token] += 1

    def dedup(values: list[str]) -> list[str]:
        return sorted(set(values))

    majors = [
        {"key": name, "classes": member_classes[name], "jobs_explicit": len(dedup(explicit.get(name, [])))}
        for name in sorted(member_classes)
        if explicit.get(name)
    ]
    classes = [
        {"key": name, "members": sorted(class_members[name]), "jobs_by_class": len(dedup(by_class.get(name, [])))}
        for name in sorted(class_members)
        if by_class.get(name)
    ]
    total = len(rows)
    touched = len(
        set().union(*[set(v) for v in explicit.values()], *[set(v) for v in by_class.values()], set(unlimited) or set())
    ) if (explicit or by_class or unlimited) else 0
    return {
        "schema": "wanyu-major-index/v1",
        "majors": majors,
        "classes": classes,
        "postings": {
            "explicit": {k: dedup(v) for k, v in sorted(explicit.items())},
            "by_class": {k: dedup(v) for k, v in sorted(by_class.items())},
            "unlimited": dedup(unlimited),
        },
        "unclassified_tokens": [{"token": token, "jobs": count} for token, count in unclassified.most_common()],
        "stats": {
            "rows": total,
            "rows_touched": touched,
            "rows_unclassified_only": total - touched,
            "explicit_terms": len(explicit),
            "class_terms": len(by_class),
            "unlimited_jobs": len(dedup(unlimited)),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="构建专业匹配倒排索引 major-index.json")
    parser.add_argument("--cycle", default="2026")
    args = parser.parse_args()

    catalog = load_json(HERE / "data" / "major_catalog.json")
    jobs_path = SITE / "data" / "cycles" / str(args.cycle) / "jobs.json"
    rows = load_json(jobs_path)["allMajors"]["rows"]
    # D2 幽灵重复行剔除口径与前端 rowsFor 一致（马鞍山 110 行，见 d2_resolution_report_20260905.txt）
    phantom = load_json(HERE / "data" / "phantom_codes_2026.json")
    rows = [r for r in rows if not (str(r.get("city")) == "马鞍山" and str(r.get("code")) in set(phantom))]
    index = build(catalog["map"], rows)
    index["cycle"] = str(args.cycle)
    index["computed_from"] = {"jobs_sha256": sha256(jobs_path)}

    out_path = SITE / "data" / "cycles" / str(args.cycle) / "major-index.json"
    out_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    stats = index["stats"]
    print(f"[{args.cycle}] major-index.json → {out_path.name}（{out_path.stat().st_size/1024:.0f}KB）")
    print(f"  岗位 {stats['rows']} | 触达 {stats['rows_touched']} | 仅未归类 {stats['rows_unclassified_only']} ({stats['rows_unclassified_only']/max(stats['rows'],1)*100:.1f}%)")
    print(f"  explicit 词条 {stats['explicit_terms']} | by_class 词条 {stats['class_terms']} | 不限 {stats['unlimited_jobs']} 岗")

    # 验收探针
    p = index["postings"]
    probe = lambda name: (len(p["explicit"].get(name, [])), len(p["by_class"].get(name, [])))
    ip, lc = probe("知识产权")[0], len(set(p["explicit"].get("知识产权", [])) | set(p["by_class"].get("法学类", [])))
    se, jc = probe("软件工程")[0], len(set(p["explicit"].get("软件工程", [])) | set(p["by_class"].get("计算机类", [])))
    kj = len(p["explicit"].get("会计学", []))
    print(f"  验收: 知识产权 explicit={ip} ∪法学类={lc} | 软件工程 explicit={se} ∪计算机类={jc} | 会计学 explicit={kj}")
    ok = lc >= 1100 and jc >= 500 and kj >= 800
    print("  RESULT:", "PASS" if ok else "CHECK-TRESHOLDS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
