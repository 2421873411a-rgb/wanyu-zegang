# -*- coding: utf-8 -*-
"""verify_sources.py —— 构建前校验数据源（对账 sources.lock.json，wanyu-source-lock/v2）。

跨平台约束：sources.lock 历史上使用 Windows 反斜杠路径；本工具统一按仓库相对
POSIX 语义解析，Windows/Linux/macOS 得到同一目标，并拒绝绝对路径和 .. 穿越。
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "项目源码" / "sources.lock.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_locked_path(value: str) -> Path:
    """把 lock 中 Windows/POSIX 相对路径安全映射到仓库根目录。"""
    normalized = str(value).replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or any(part == ".." for part in pure.parts):
        raise ValueError(f"sources.lock 含非法路径: {value!r}")
    parts = [part for part in pure.parts if part not in ("", ".")]
    if not parts:
        raise ValueError(f"sources.lock 含空路径: {value!r}")
    return ROOT.joinpath(*parts)


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
    parser.parse_args()

    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    sources = lock.get("sources")
    if not isinstance(sources, list) or not sources:
        print("SOURCE LOCK INVALID：sources 必须为非空数组")
        return 3

    bad: list[str] = []
    missing: list[str] = []
    checked = 0
    try:
        for source in sources:
            source_id = str(source.get("id") or "<missing-id>")
            p = resolve_locked_path(str(source.get("path") or ""))
            if not p.exists():
                missing.append(source_id)
                continue
            if source.get("sha256"):
                checked += 1
                if sha256(p) != source["sha256"] or p.stat().st_size != source.get("bytes"):
                    bad.append(source_id)
            elif source.get("rollup_sha256"):
                checked += 1
                actual, file_count, total_bytes = rollup(p)
                if (
                    total_bytes != source.get("bytes")
                    or file_count != source.get("files")
                    or actual != source["rollup_sha256"]
                ):
                    bad.append(f"{source_id}(rollup)")
            else:
                bad.append(f"{source_id}(无可验证哈希——锁文件非法)")
    except (TypeError, ValueError) as exc:
        print(f"SOURCE LOCK INVALID：{exc}")
        return 3

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
