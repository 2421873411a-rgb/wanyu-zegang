"""Sync the supplement evidence module into existing site outputs.

The full maintainable builder still depends on source page artifacts that are
not present in the handoff package.  This small, deterministic sync keeps the
already-validated canonical JSON untouched while refreshing only the evidence
module, shell assets, and manifest entries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from .build_supplement_evidence import build_supplement_evidence
except ImportError:  # pragma: no cover - supports direct script execution
    from tools.anhui_web.build_supplement_evidence import build_supplement_evidence


RELEASE_QUERY = "17.6.4-supplement-evidence"


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def _sync_one(root: Path, output_dir: Path, payload: dict[str, object]) -> dict[str, object]:
    output_dir = output_dir.resolve()
    evidence_path = output_dir / "data" / "audit" / "supplement-20260904.json"
    encoded = _json_bytes(payload)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_bytes(encoded)

    manifest_path = output_dir / "data" / "site-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["supplement"] = {
        "data": "data/audit/supplement-20260904.json",
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "schema": payload.get("schema"),
        "source": "source_data/supplement_20260904",
    }
    source_chain = manifest.setdefault("source_chain", {})
    source_chain["supplement_evidence"] = "tools/anhui_web/build_supplement_evidence.py"
    manifest_path.write_bytes(_json_bytes(manifest))

    template_dir = root / "tools" / "anhui_web" / "templates"
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for name in ("maintainable-site.js", "v17-tools.js"):
        shutil.copyfile(template_dir / name, assets_dir / name)
    shutil.copyfile(template_dir / "maintainable-sw.js", output_dir / "sw.js")
    index_path = output_dir / "index.html"
    index = index_path.read_text(encoding="utf-8")
    index = index.replace("v17-tools.js?v=17.6.4-exam-scope", f"v17-tools.js?v={RELEASE_QUERY}")
    index = index.replace("maintainable-site.js?v=17.6.4-exam-scope", f"maintainable-site.js?v={RELEASE_QUERY}")
    index = index.replace("v17-tools.js?v=v17.6.4-supplement-evidence", f"v17-tools.js?v={RELEASE_QUERY}")
    index = index.replace("maintainable-site.js?v=v17.6.4-supplement-evidence", f"maintainable-site.js?v={RELEASE_QUERY}")
    index_path.write_text(index, encoding="utf-8")
    return {
        "output": str(output_dir),
        "evidence_bytes": len(encoded),
        "evidence_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def sync_supplement_evidence(root: Path = ROOT) -> list[dict[str, object]]:
    root = Path(root).resolve()
    payload = build_supplement_evidence(root)
    source_path = root / "source_data" / "supplement_20260904" / "integrity_audit.json"
    source_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_dirs = [
        root / "deliverables" / "maintainable",
        root.parent.parent / "wan-full-update" / "site",
        root.parent.parent / "wan-lite" / "site",
    ]
    results = []
    for output_dir in output_dirs:
        if not (output_dir / "data" / "site-manifest.json").is_file():
            continue
        results.append(_sync_one(root, output_dir, payload))
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="同步 supplement_20260904 证据模块到当前站点输出")
    parser.add_argument("--root", type=Path, default=ROOT, help="项目根目录")
    args = parser.parse_args()
    print(json.dumps(sync_supplement_evidence(args.root), ensure_ascii=False))
