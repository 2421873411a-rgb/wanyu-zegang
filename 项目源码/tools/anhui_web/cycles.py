"""数据周期清单读取器（v10 多周期工作台地基）。

manifest.json 声明当前数据周期、快照日期、数据集文件与开放核查项；
构建脚本与测试通过本模块获取周期元信息，避免散落硬编码。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"

REQUIRED_FIELDS = ("version", "cycle", "snapshot_date", "sources", "datasets")


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    """读取并校验周期清单；缺少必需字段时抛出带字段名的 ValueError。"""
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [field for field in REQUIRED_FIELDS if field not in manifest]
    if missing:
        raise ValueError(f"manifest.json 缺少必需字段：{missing}")
    return manifest


def resolve_dataset(manifest: dict[str, Any], key: str, data_dir: Path = DATA_DIR) -> Path:
    """按清单解析数据集文件路径；键不存在时抛出 KeyError。"""
    datasets = manifest.get("datasets") or {}
    if key not in datasets:
        raise KeyError(f"manifest.json datasets 中没有 {key}")
    return data_dir / str(datasets[key])


def cycle_label(manifest: dict[str, Any]) -> str:
    """生成人读周期标签，如 `数据周期 2026 · 快照 2026-08-28`。"""
    return f"数据周期 {manifest['cycle']} · 快照 {manifest['snapshot_date']}"


if __name__ == "__main__":
    print(cycle_label(load_manifest()))
