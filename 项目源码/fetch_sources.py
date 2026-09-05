# -*- coding: utf-8 -*-
"""阶段 H：fetch_sources.py —— 构建前校验数据源（对账 sources.lock.json）。

用法：
  python fetch_sources.py --verify   # 校验本机源文件与锁一致（构建前必跑）
说明：大体积源数据暂存于本机+COS 月备；COS 凭据绝不入库。缺源时明确报
  source unavailable，禁止用旧缓存静默继续构建。
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    lock = json.loads((ROOT / "项目源码" / "sources.lock.json").read_text(encoding="utf-8"))
    bad, missing = [], []
    for s in lock["sources"]:
        p = ROOT / s["path"]
        if not p.exists():
            missing.append(s["id"])
            continue
        if s.get("sha256"):
            if sha256(p) != s["sha256"] or p.stat().st_size != s.get("bytes"):
                bad.append(s["id"])
    if missing:
        print("SOURCE UNAVAILABLE（缺源，禁止构建发布）:", missing)
        return 2
    if bad:
        print("SOURCE MISMATCH（哈希/字节数不符，禁止构建发布）:", bad)
        return 1
    print(f"sources.lock 校验通过：{len(lock['sources'])} 项全部一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
