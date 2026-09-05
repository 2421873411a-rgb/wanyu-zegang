# -*- coding: utf-8 -*-
"""生成 sources.lock.json（wanyu-source-lock/v2，可重复构建数据锁）。

锁定范围：站点数据构建的关键输入（源 Word 报告、收割侧料、专业目录、原始附件清单、
审计真源 three_year_audit.json、生命周期输入 record_status_overrides.json）。
目录级登记（source_data/、raw_syb_fugao/）必须带可重复计算的 rollup_sha256：
  按相对路径排序 → 逐文件 "relpath\\0sha256\\0bytes\\n" 拼接 → 整体 sha256。
大体积原始证据不入 git（体积），但内容必须可验证（rollup）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "项目源码" / "tools" / "anhui_web" / "data"
SRC = ROOT / "项目源码" / "source_data"

KEY_FILES = [
    DATA / "major_catalog.json",
    DATA / "huatu_syb_2026.json",
    DATA / "score_lists.json",
    DATA / "syb2026_daxian_all.json",
    DATA / "syb2026_daxian_all.pre_fix.json",
    DATA / ".zhaokao_syb_scan.json",
    DATA / "ahsk2026_hire.json",
    DATA / "phantom_codes_2026.json",
    DATA / "three_year_audit.json",
    DATA / "record_status_overrides.json",
]

ROLLUP_ALGO = "sha256(relpath\\0file_sha256\\0bytes\\n sorted by relpath)"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dir_rollup(path: Path) -> dict:
    files = [p for p in path.rglob("*") if p.is_file()]
    entries: list[bytes] = []
    total = 0
    for p in sorted(files, key=lambda item: item.relative_to(path).as_posix()):
        rel = p.relative_to(path).as_posix()
        size = p.stat().st_size
        total += size
        entries.append(f"{rel}\0{sha256(p)}\0{size}\n".encode("utf-8"))
    digest = hashlib.sha256(b"".join(entries)).hexdigest()
    return {"files": len(files), "bytes": total, "root": path.name, "rollup_sha256": digest}


def main() -> int:
    sources = []
    missing = []
    for f in KEY_FILES:
        if f.is_file():
            sources.append({"id": f.name, "path": str(f.relative_to(ROOT)), "sha256": sha256(f),
                            "bytes": f.stat().st_size, "required": True})
        else:
            missing.append(str(f))
    for d in (SRC, DATA / "raw_syb_fugao"):
        if d.is_dir():
            st = dir_rollup(d)
            sources.append({"id": f"dir:{st['root']}", "path": str(d.relative_to(ROOT)),
                            "bytes": st["bytes"], "files": st["files"],
                            "rollup_sha256": st["rollup_sha256"],
                            "required": True, "hash_level": "directory_rollup",
                            "rollup_algo": ROLLUP_ALGO})
        else:
            missing.append(str(d))
    lock = {"schema": "wanyu-source-lock/v2", "snapshot": "2026-09-05", "sources": sources}
    out = ROOT / "项目源码" / "sources.lock.json"
    out.write_text(json.dumps(lock, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    file_count = sum(1 for s in sources if not s["id"].startswith("dir:"))
    print(f"sources.lock.json：文件级 {file_count} + 目录级 {len(sources) - file_count}（均含可验证哈希）")
    if missing:
        print("缺失（登记为 required 但当前不在盘）:", missing)
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
