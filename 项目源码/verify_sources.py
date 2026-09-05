# -*- coding: utf-8 -*-
"""verify_sources.py —— 构建前校验数据源（对账 sources.lock.json，wanyu-source-lock/v2）。

用法：
  python verify_sources.py            # 校验本机源文件与锁一致（构建前必跑）
说明：
- 文件级：校验 sha256 + bytes。
- 目录级：校验目录存在 + 文件数 + 总字节 + rollup_sha256（与生成算法一致，
  "目录存在=一致" 的假锁在 v2 已废除——内容被替换必然导致 rollup 不符）。
- 大体积源数据暂存本机 + COS 月备；COS 凭据绝不入库。缺源时明确报
  SOURCE UNAVAILABLE，禁止用旧缓存静默继续构建。真正的自动 fetch（COS URI +
  version ID）待 v17.9+ 落地，本脚本只做校验，不做下载。
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "项目源码" / "sources.lock.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rollup(path: Path) -> tuple[str, int, int]:
    """Deterministic directory rollup: (digest, file_count, total_bytes)."""
    files = [p for p in path.rglob("*") if p.is_file()]
    entries: list[bytes] = []
    total = 0
    for p in sorted(files, key=lambda item: item.relative_to(path).as_posix()):
        rel = p.relative_to(path).as_posix()
        size = p.stat().st_size
        total += size
        entries.append(f"{rel}\0{sha256(p)}\0{size}\n".encode("utf-8"))
    return hashlib.sha256(b"".join(entries)).hexdigest(), len(files), total


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 sources.lock 数据源（v2：含目录 rollup）")
    parser.add_argument("--verify", action="store_true", help="兼容旧参数；本工具只做校验")
    args = parser.parse_args()
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    bad, missing = [], []
    checked = 0
    for s in lock["sources"]:
        p = ROOT / s["path"]
        if not p.exists():
            missing.append(s["id"])
            continue
        if s.get("sha256"):
            checked += 1
            if sha256(p) != s["sha256"] or p.stat().st_size != s.get("bytes"):
                bad.append(s["id"])
        elif s.get("rollup_sha256"):
            checked += 1
            actual, file_count, total_bytes = rollup(p)
            if total_bytes != s.get("bytes") or file_count != s.get("files") or actual != s["rollup_sha256"]:
                bad.append(f"{s['id']}(rollup)")
        else:
            bad.append(f"{s['id']}(无可验证哈希——锁文件非法)")
    if missing:
        print("SOURCE UNAVAILABLE（缺源，禁止构建发布）:", missing)
        return 2
    if bad:
        print("SOURCE MISMATCH（哈希/字节数/rollup 不符，禁止构建发布）:", bad)
        return 1
    print(f"sources.lock 校验通过：{checked} 项全部一致（文件 sha256 + 目录 rollup）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
