# -*- coding: utf-8 -*-
"""verify_sources.py —— 校验 sources.lock（wanyu-source-lock/v2）。

完整模式用于发布机：要求所有外部/本地大体积源存在并逐项校验 sha256/rollup。
`--manifest-only` 用于 GitHub hosted CI：只校验 lock 结构、跨平台安全相对路径、
哈希/字节数字段合法性；它不会冒充“已校验外部 source_data 内容”。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "项目源码" / "sources.lock.json"
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_locked_path(value: str) -> Path:
    normalized = str(value).replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or any(part == ".." for part in pure.parts):
        raise ValueError(f"sources.lock 含非法路径: {value!r}")
    parts = [part for part in pure.parts if part not in ("", ".")]
    if not parts:
        raise ValueError(f"sources.lock 含空路径: {value!r}")
    return ROOT.joinpath(*parts)


def rollup(path: Path) -> tuple[str, int, int]:
    files = [p for p in path.rglob("*") if p.is_file()]
    entries: list[bytes] = []
    total = 0
    for p in sorted(files, key=lambda item: item.relative_to(path).as_posix()):
        rel = p.relative_to(path).as_posix()
        size = p.stat().st_size
        total += size
        entries.append(f"{rel}\0{sha256(p)}\0{size}\n".encode("utf-8"))
    return hashlib.sha256(b"".join(entries)).hexdigest(), len(files), total


def validate_manifest(lock: dict) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    if lock.get("schema") != "wanyu-source-lock/v2":
        errors.append(f"schema 非 wanyu-source-lock/v2: {lock.get('schema')!r}")
    sources = lock.get("sources")
    if not isinstance(sources, list) or not sources:
        return [], errors + ["sources 必须为非空数组"]

    seen: set[str] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"sources[{index}] 不是对象")
            continue
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id.strip():
            errors.append(f"sources[{index}].id 缺失")
        elif source_id in seen:
            errors.append(f"source id 重复: {source_id}")
        else:
            seen.add(source_id)
        try:
            resolve_locked_path(str(source.get("path") or ""))
        except ValueError as exc:
            errors.append(str(exc))

        size = source.get("bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            errors.append(f"{source_id}: bytes 非非负整数")
        file_sha = source.get("sha256")
        dir_sha = source.get("rollup_sha256")
        if bool(file_sha) == bool(dir_sha):
            errors.append(f"{source_id}: 必须且只能提供 sha256 / rollup_sha256 之一")
        chosen_sha = file_sha or dir_sha
        if not isinstance(chosen_sha, str) or not SHA_RE.fullmatch(chosen_sha):
            errors.append(f"{source_id}: 哈希必须为 64 位小写十六进制")
        if dir_sha:
            files = source.get("files")
            if not isinstance(files, int) or isinstance(files, bool) or files < 0:
                errors.append(f"{source_id}: directory rollup 的 files 非非负整数")
    return sources, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 sources.lock 数据源")
    parser.add_argument("--verify", action="store_true", help="兼容旧参数；默认即完整校验")
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="只校验 lock 结构与路径/哈希格式，不要求外部源在本机存在",
    )
    args = parser.parse_args()

    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    sources, manifest_errors = validate_manifest(lock)
    if manifest_errors:
        for error in manifest_errors:
            print("SOURCE LOCK INVALID:", error)
        return 3
    if args.manifest_only:
        print(f"sources.lock manifest PASS：{len(sources)} 项结构/路径/哈希格式合法（未声称外部源内容已校验）")
        return 0

    bad: list[str] = []
    missing: list[str] = []
    checked = 0
    for source in sources:
        source_id = str(source["id"])
        p = resolve_locked_path(str(source["path"]))
        if not p.exists():
            missing.append(source_id)
            continue
        if source.get("sha256"):
            checked += 1
            if sha256(p) != source["sha256"] or p.stat().st_size != source.get("bytes"):
                bad.append(source_id)
        else:
            checked += 1
            actual, file_count, total_bytes = rollup(p)
            if (
                total_bytes != source.get("bytes")
                or file_count != source.get("files")
                or actual != source["rollup_sha256"]
            ):
                bad.append(f"{source_id}(rollup)")

    if missing:
        print("SOURCE UNAVAILABLE（缺源，禁止构建发布）:", missing)
        return 2
    if bad:
        print("SOURCE MISMATCH（哈希/字节数/rollup 不符，禁止构建发布）:", bad)
        return 1
    print(f"sources.lock 完整校验通过：{checked} 项全部一致（文件 sha256 + 目录 rollup）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
