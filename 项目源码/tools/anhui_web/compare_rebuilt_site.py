#!/usr/bin/env python3
"""重建等价比对（审计 FE-002/F-017）：干净重建产物必须逐字节复现已发布网站。

与裸 `diff -r` 的差异：部署期伴生的 .gz 与 supplement 证据链（依赖仅发布机持有的
source_data/supplement_20260904）被显式归一——site-manifest.json 在双方都弹出
supplement 键后比较，supplement 数据文件跳过并在报告中注明。

用法：python tools/anhui_web/compare_rebuilt_site.py <rebuilt_dir> <released_dir>
漂移 → exit 1 并列出清单。
"""
import json
import sys
from pathlib import Path

SKIP_FILES = {"data/audit/supplement-20260904.json"}
SKIP_SUFFIXES = {".gz"}
NORMALIZE_JSON = {"data/site-manifest.json"}


def load_normalized(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc.pop("supplement", None)
    return doc


def compare(rebuilt: Path, released: Path) -> list[str]:
    drifts: list[str] = []
    rebuilt_files = {
        p.relative_to(rebuilt).as_posix()
        for p in rebuilt.rglob("*") if p.is_file()
        and p.suffix not in SKIP_SUFFIXES
        and p.relative_to(rebuilt).as_posix() not in SKIP_FILES
    }
    released_files = {
        p.relative_to(released).as_posix()
        for p in released.rglob("*") if p.is_file()
        and p.suffix not in SKIP_SUFFIXES
        and p.relative_to(released).as_posix() not in SKIP_FILES
    }
    for name in sorted(rebuilt_files - released_files):
        drifts.append(f"重建多出：{name}（发布站缺失）")
    for name in sorted(released_files - rebuilt_files):
        drifts.append(f"重建缺失：{name}（发布站存在）")
    for name in sorted(rebuilt_files & released_files):
        left, right = rebuilt / name, released / name
        if name in NORMALIZE_JSON:
            if load_normalized(left) != load_normalized(right):
                drifts.append(f"内容漂移（归一化后仍不等）：{name}")
            continue
        if left.read_bytes() != right.read_bytes():
            drifts.append(f"字节漂移：{name}")
    return drifts


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    rebuilt, released = Path(sys.argv[1]), Path(sys.argv[2])
    drifts = compare(rebuilt, released)
    if drifts:
        print(f"rebuild parity: FAIL（{len(drifts)} 处；supplement 链已归一）")
        for item in drifts[:50]:
            print(f"  - {item}")
        return 1
    print("rebuild parity: PASS（除 .gz 伴生与 supplement 证据链外逐字节一致）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
