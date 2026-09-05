"""Write the deterministic human-readable manifest for the v14 handoff."""

from __future__ import annotations

import argparse
import hashlib
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(root: Path = ROOT, generated: str | None = None) -> str:
    root = Path(root).resolve()
    files = [
        root / "deliverables" / "皖域择岗总览.html",
        root / "deliverables" / "HANDOFF.md",
        root / "deliverables" / "CHANGELOG.md",
        root / "docs" / "数据字典.md",
        root / "docs" / "数据更新操作手册.md",
        root / "docs" / "长期维护网站架构方案_v2.md",
        root / "docs" / "三年数据真实性与完整性审计_v14.md",
        root / "deliverables" / "releases" / "v14.0" / "manifest.json",
        root / "tools" / "anhui_web" / "build_maintainable_site.py",
        root / "tools" / "anhui_web" / "build_map.py",
        root / "tools" / "anhui_web" / "verify_maintainable_site.py",
        root / "tools" / "anhui_web" / "release.py",
        root / "tests" / "maintainable_browser_smoke.js",
        root / "tests" / "test_map_restore.py",
    ]
    maintainable = root / "deliverables" / "maintainable"
    if maintainable.is_dir():
        files.extend(path for path in maintainable.rglob("*") if path.is_file())
    unique = sorted({path.resolve() for path in files if path.is_file()})
    lines = [f"皖域择岗档案 v14.0 · formal manifest", f"generated: {generated or date.today().isoformat()}", "hash: SHA-256", ""]
    for path in unique:
        relative = path.relative_to(root).as_posix()
        lines.append(f"{relative}|{path.stat().st_size}|{sha256(path)}")
    lines.append("")
    return "\n".join(lines)


def write_manifest(root: Path = ROOT, generated: str | None = None) -> Path:
    root = Path(root).resolve()
    path = root / "deliverables" / "MANIFEST.txt"
    path.write_text(build_manifest(root, generated), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="写入 v14.0 交接清单")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    print(write_manifest(args.root, args.date))
