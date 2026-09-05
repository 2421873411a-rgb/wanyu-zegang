# -*- coding: utf-8 -*-
"""Generate per-position candidate score lists for the offline workbench.

The legacy ``bs``/``ms`` maps are retained for compatibility, while ``by_key``
is the authoritative lookup for the UI. Its key is
``exam|city|code|recruits`` so reused position codes cannot silently bind to a
different city or exam category.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
_PKG_SRC = ROOT / "source_data" / "anhui2026"
_SRC_ENV = os.environ.get("WANYU2_SRC", "").strip()
SRC = Path(_SRC_ENV) if _SRC_ENV else _PKG_SRC
RAW = HERE / "data" / "raw_syb_fugao"
OUT = HERE / "data" / "score_lists.json"


def cycle_paths(cycle: str) -> dict[str, Path]:
    """Resolve source, raw score attachments, and output for one data cycle."""
    cycle = str(cycle)
    if cycle == "2026":
        return {"source": Path(_SRC_ENV) if _SRC_ENV else _PKG_SRC,
                "raw": RAW, "output": OUT}
    source = ROOT / "source_data" / f"anhui{cycle}"
    return {"source": source, "raw": source / "raw",
            "output": HERE / "data" / "cycles" / cycle / "score_lists.json"}


def _source_snapshot_date(cycle: str) -> str:
    """Return a stable date from the cycle manifest, never today's build date.

    Score lists are frozen inputs for the single-file release gate.  Stamping
    them with ``date.today()`` makes an identical source bundle look changed
    every midnight, so the stamp must follow the source snapshot instead.
    """
    cycle = str(cycle)
    metadata_path = (HERE / "data" / "manifest.json" if cycle == "2026"
                     else HERE / "data" / "cycles" / cycle / "cycle.json")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata = {}
    for key in ("generated_on", "release_date", "snapshot_date"):
        value = str(metadata.get(key) or "").strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return value
    return "undated-source"


def score_key(exam: str, city: str, code: str, recruits: object | None = None) -> str:
    """Build the stable UI key; all fields are stringified for JSON/JS parity."""
    parts = [str(exam or ""), str(city or ""), str(code or "")]
    if recruits is not None:
        parts.append(str(recruits))
    return "|".join(parts)


def _locate_header(df: pd.DataFrame):
    """Return (header row, position-code column, ticket column, score column)."""
    for i in range(min(12, len(df))):
        txt = "".join(str(x) for x in df.iloc[i].tolist())
        if ("岗位代码" in txt or "职位代码" in txt) and ("成绩" in txt or "分数" in txt):
            hdr = [re.sub(r"\s", "", str(x)) for x in df.iloc[i].tolist()]
            code_ci = zkz_ci = None
            score_cols = []
            for ci, h in enumerate(hdr):
                if code_ci is None and ("岗位代码" in h or "职位代码" in h):
                    code_ci = ci
                if "准考证" in h:
                    zkz_ci = ci
                if "成绩" in h or "分数" in h:
                    score_cols.append(ci)
            if code_ci is None or not score_cols:
                continue
            si = next((c for c in score_cols if "笔试成绩" in hdr[c]),
                      next((c for c in score_cols if "综合成绩" in hdr[c]), score_cols[-1]))
            return i, code_ci, zkz_ci, si
    return None


def _rows_of(df: pd.DataFrame):
    loc = _locate_header(df)
    if loc is None:
        return None
    hrow, code_ci, zkz_ci, si = loc
    df2 = df.iloc[hrow + 1:].copy()
    df2.columns = range(len(df.columns))
    df2["code"] = df2[code_ci].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df2 = df2[df2["code"].str.match(r"^\d{6,8}$", na=False)]
    df2["score"] = pd.to_numeric(df2[si], errors="coerce")
    df2 = df2.dropna(subset=["score"])
    if not len(df2):
        return None
    zk = df2[zkz_ci].astype(str).str.strip() if zkz_ci is not None else None
    out: dict[str, list] = {}
    for idx, row in df2.iterrows():
        ticket = str(zk.loc[idx]).strip() if zk is not None and str(zk.loc[idx]) not in ("nan", "") else ""
        out.setdefault(str(row["code"]), []).append([round(float(row["score"]), 2), ticket])
    return out


def _read_positions(path: Path, exam: str) -> dict[tuple[str, str], list[dict[str, object]]]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], list[dict[str, object]]] = {}
    for position in payload.get("positions", []):
        code = str(position.get("code") or position.get("职位代码") or "").strip()
        city = str(position.get("city") or position.get("region") or "").strip()
        if not code or not city:
            continue
        recruits = position.get("num", position.get("recruits", 0))
        out.setdefault((exam, code), []).append({
            "exam": exam, "city": city, "code": code, "recruits": recruits,
            "unit": str(position.get("unit") or ""),
            "zy": str(position.get("zy") or position.get("zhuanye") or ""),
            "cycle": str(position.get("cycle") or ""),
            "reg": str(position.get("reg") or ""),
        })
    return out


def _position_index(cycle: str) -> dict[tuple[str, str], list[dict[str, object]]]:
    data_dir = HERE / "data" if cycle == "2026" else HERE / "data" / "cycles" / cycle
    index: dict[tuple[str, str], list[dict[str, object]]] = {}
    files = ((data_dir / f"all_majors_{cycle}.json", "省考"),
             (data_dir / f"guokao{cycle}.json", "国考"),
             (data_dir / f"huatu_syb_{cycle}.json", "事业编"))
    for path, exam in files:
        for key, values in _read_positions(path, exam).items():
            index.setdefault(key, []).extend(values)
    return index


def _keyed_scores(code_scores: dict[str, list], exam: str,
                  index: dict[tuple[str, str], list[dict[str, object]]]):
    keyed: dict[str, list] = {}
    unresolved: list[dict[str, object]] = []
    for code, rows in code_scores.items():
        candidates = index.get((exam, str(code)), [])
        if not candidates:
            continue
        # The source score attachment has no city column. Even when the
        # duplicated rows happen to share the same visible fields, binding
        # the same list to multiple position records would be an unproven
        # city-level claim. Keep only uniquely identifiable joins.
        if len(candidates) != 1:
            unresolved.append({
                "exam": exam,
                "code": str(code),
                "candidates": [score_key(exam, c["city"], code, c["recruits"]) for c in candidates],
                "reason": "source score attachment has no city and duplicate code candidates are ambiguous",
            })
            continue
        for candidate in candidates:
            keyed[score_key(exam, candidate["city"], code, candidate["recruits"])] = rows
    return keyed, unresolved


def _legacy_bs(src: Path) -> dict[str, list]:
    frame = pd.read_csv(src / "shengkao_bishi_mingdan.csv", dtype=str).fillna("")
    frame["_score"] = pd.to_numeric(frame["笔试合成成绩"], errors="coerce")
    frame = frame.dropna(subset=["_score"])
    out: dict[str, list] = {}
    for code, group in frame.groupby("职位代码"):
        rows = [[round(float(score), 2), str(ticket).strip()]
                for score, ticket in zip(group["_score"], group["准考证号"])]
        out[str(code).strip()] = sorted(rows, key=lambda x: -x[0])
    return out


def _legacy_ms(src: Path) -> dict[str, list]:
    frame = pd.read_csv(src / "shengkao_mianshi_zongchengji.csv", dtype=str).fillna("")
    for column in ("笔试成绩", "面试成绩", "考试总成绩"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["考试总成绩"])
    out: dict[str, list] = {}
    for code, group in frame.groupby("职位代码"):
        rows = [[round(float(row["考试总成绩"]), 2),
                 round(float(row["笔试成绩"]), 2) if pd.notna(row["笔试成绩"]) else None,
                 round(float(row["面试成绩"]), 2) if pd.notna(row["面试成绩"]) else None,
                 str(row["准考证号"]).strip()] for _, row in group.iterrows()]
        out[str(code).strip()] = sorted(rows, key=lambda x: -(x[0] or 0))
    return out


def _merge_syb_scores(raw: Path, cycle: str) -> tuple[dict[str, list], int]:
    bs: dict[str, list] = {}
    people = 0
    if not raw.is_dir():
        return bs, people
    paths = sorted(raw.glob("syb_*") if cycle == "2026" else raw.glob("*"))
    for path in paths:
        if path.suffix.lower() not in (".xls", ".xlsx"):
            continue
        try:
            book = pd.read_excel(path, sheet_name=None, header=None)
        except Exception:
            continue
        best = None
        for frame in book.values():
            current = _rows_of(frame)
            if current and (best is None or sum(map(len, current.values())) > sum(map(len, best.values()))):
                best = current
        if not best:
            continue
        for code, rows in best.items():
            bs.setdefault(code, []).extend(rows)
            people += len(rows)
    for code, rows in bs.items():
        seen = set()
        unique = []
        for score, ticket in sorted(rows, key=lambda x: -x[0]):
            if (score, ticket) not in seen:
                seen.add((score, ticket))
                unique.append([score, ticket])
        bs[code] = unique
    return bs, people


def main(cycle: str = "2026") -> int:
    cycle = str(cycle)
    paths = cycle_paths(cycle)
    source = paths["source"]
    if not source.is_dir():
        raise FileNotFoundError(f"source directory not found: {source}")
    province_bs = _legacy_bs(source)
    ms = _legacy_ms(source)
    print("省考笔试 posts:", len(province_bs), "people:", sum(map(len, province_bs.values())))
    print("省考面试 posts:", len(ms), "people:", sum(map(len, ms.values())))
    syb_bs, syb_people = _merge_syb_scores(paths["raw"], cycle)
    print("事业编补充 people:", syb_people)
    # Keep the historical code-only map for old consumers, but never use it
    # to create keyed rows because it mixes exam categories by design.
    bs = {code: list(rows) for code, rows in province_bs.items()}
    for code, rows in syb_bs.items():
        bs.setdefault(code, []).extend(rows)

    index = _position_index(cycle)
    bs_keyed, bs_unresolved = _keyed_scores(province_bs, "省考", index)
    ms_keyed, ms_unresolved = _keyed_scores(ms, "省考", index)
    syb_keyed, syb_unresolved = _keyed_scores(syb_bs, "事业编", index)
    by_key: dict[str, dict[str, list]] = {}
    for key, rows in bs_keyed.items():
        by_key.setdefault(key, {})["bs"] = rows
    for key, rows in ms_keyed.items():
        by_key.setdefault(key, {})["ms"] = rows
    for key, rows in syb_keyed.items():
        by_key.setdefault(key, {})["bs"] = rows
    unresolved = bs_unresolved + ms_unresolved + syb_unresolved
    payload = {
        "cycle": cycle, "generated_on": _source_snapshot_date(cycle),
        "bs": bs, "ms": ms, "by_key": by_key,
        "keyed": {
            "bs": sum(1 for value in by_key.values() if value.get("bs")),
            "ms": sum(1 for value in by_key.values() if value.get("ms")),
            "unresolved": unresolved,
        },
    }
    output = paths["output"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size = output.stat().st_size / 1048576
    print(f"wrote {output.name} {size:.1f} MB, bs posts={len(bs)}, ms posts={len(ms)}, keyed={len(by_key)}, unresolved={len(unresolved)}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成逐岗考生成绩名单（按考试/城市/代码复合键输出）。")
    parser.add_argument("--cycle", default="2026", help="数据周期：2026、2025 或 2024")
    raise SystemExit(main(parser.parse_args().cycle))
