# -*- coding: utf-8 -*-
"""全链哈希重发布工具：数据文件变动后一键同步 site-manifest + job_history 绑定。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[3] / "网站"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    mp = SITE / "data" / "site-manifest.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    touched = 0
    for c in m.get("cycles", []):
        year = str(c["cycle"])
        for name, entry in (c.get("modules") or {}).items():
            p = SITE / str(entry.get("data") or "")
            if not p.is_file():
                continue
            new_bytes, new_sha = p.stat().st_size, sha256(p)
            if entry.get("sha256") != new_sha:
                entry["bytes"], entry["sha256"] = new_bytes, new_sha
                touched += 1
        jp = SITE / "data" / "cycles" / year / "jobs.json"
        if jp.is_file():
            c["data"] = f"data/cycles/{year}/jobs.json"
            c["bytes"] = jp.stat().st_size
            c["sha256"] = sha256(jp)
    for name, entry in m.items():
        if isinstance(entry, dict) and entry.get("data") and entry.get("sha256"):
            p = SITE / str(entry["data"])
            if p.is_file():
                new_bytes, new_sha = p.stat().st_size, sha256(p)
                if entry.get("sha256") != new_sha:
                    entry["bytes"], entry["sha256"] = new_bytes, new_sha
                    touched += 1
    jhp = SITE / "data" / "job_history.json"
    if jhp.is_file():
        jh = json.loads(jhp.read_text(encoding="utf-8"))
        for cyc, source in (jh.get("sources") or {}).items():
            jp = SITE / str(source.get("data") or "")
            if jp.is_file():
                source["sha256"] = sha256(jp)
        jhp.write_text(json.dumps(jh, ensure_ascii=False, indent=1), encoding="utf-8")
        e = m.get("job_history")
        if isinstance(e, dict):
            e["bytes"], e["sha256"] = jhp.stat().st_size, sha256(jhp)
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"republish_hashes: {touched} 个模块哈希已更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
