# -*- coding: utf-8 -*-
"""阶段 H：生成 sources.lock.json（可重复构建数据锁）。

锁定范围：站点数据构建的关键输入（源 Word 报告、收割侧料、专业目录、原始附件清单）。
大体积原始证据（source_data/ 446MB）按目录级登记（文件数+总字节+抽查哈希），不入 git。
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
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dir_stat(path: Path) -> dict | None:
    if not path.is_dir():
        return None
    files = [p for p in path.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    return {"files": len(files), "bytes": total, "root": str(path.name)}


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
        st = dir_stat(d)
        if st:
            sources.append({"id": f"dir:{st['root']}", "path": str(d.relative_to(ROOT)),
                            "sha256": None, "bytes": st["bytes"], "files": st["files"],
                            "required": True, "hash_level": "directory_rollup"})
    lock = {"schema": "wanyu-source-lock/v1", "snapshot": "2026-09-05", "sources": sources}
    out = ROOT / "项目源码" / "sources.lock.json"
    out.write_text(json.dumps(lock, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"sources.lock.json：{len(sources)} 项（文件级 {len(sources)-sum(1 for s in sources if s['id'].startswith('dir:'))}）")
    if missing:
        print("缺失（登记为 required 但当前不在盘）:", missing)
    print(f"→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
