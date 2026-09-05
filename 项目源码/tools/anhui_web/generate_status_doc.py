# -*- coding: utf-8 -*-
"""generate_status_doc.py —— 从版本/数据真源生成 docs/current-status.md（RC3-Q）。

真源：项目源码/release.json + 网站/data/site-manifest.json + 网站/data/audit/review-queue.json。
README 不再人工抄任何关键数字，只引用本文档。

用法：
  python tools/anhui_web/generate_status_doc.py           # 生成/覆盖 docs/current-status.md
  python tools/anhui_web/generate_status_doc.py --check   # 门禁模式：与已提交版本逐字一致，否则非 0 退出
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
WORKSPACE = PROJECT_ROOT.parent
SITE = WORKSPACE / "网站"
OUT = WORKSPACE / "docs" / "current-status.md"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def render() -> str:
    release = load(PROJECT_ROOT / "release.json")
    manifest = load(SITE / "data" / "site-manifest.json")
    rq = load(SITE / "data" / "audit" / "review-queue.json")
    lines = [
        "# 皖域择岗 · 当前状态（由真源自动生成，勿手改）",
        "",
        f"> 生成器：`项目源码/tools/anhui_web/generate_status_doc.py`；真源：release.json + site-manifest.json + review-queue.json。",
        f"> 真源快照：release **{release['release']}** · asset **{release['asset_version']}** · SW **{release['service_worker_version']}** · 数据快照 {manifest.get('snapshot_date')}。",
        "",
        "## 口径（wanyu-metrics/v1）",
        "",
        "| 周期 | raw_posts | active_posts | excluded_posts | raw_recruits | recruits（有效） | score_unresolved |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in manifest.get("cycles", []):
        lines.append(
            f"| {entry['cycle']} | {entry.get('raw_posts')} | {entry.get('active_posts')} | "
            f"{entry.get('excluded_posts')} | {entry.get('raw_recruits')} | {entry.get('recruits')} | {entry.get('score_unresolved')} |"
        )
    summary = rq.get("summary") or {}
    lines += [
        "",
        "## 复核队列",
        "",
        f"- open 事件：**{summary.get('open_event_count', summary.get('event_count'))}**（high_risk {summary.get('open_high_risk_count', summary.get('high_risk_count'))}）",
        f"- resolved 历史：**{summary.get('resolved_event_count', 0)}** 项（resolved_score_count={summary.get('resolved_score_count', 0)}，unresolved_score_count={summary.get('unresolved_score_count', 0)}）",
        f"- 公开边界（manifest gaps 合计）：**{summary.get('public_boundary_count')}**",
        "",
        "## 边界声明",
        "",
        "- `posts` 是 `active_posts` 的兼容别名（deprecated），用户口径=active；raw_* 仅审计层。",
        "- canonical 周期包为唯一正式数据输入（migration_origin=audited_production_snapshot，见 docs/migrations/canonical-seed-20260905.md）。",
        "- HTML 永远只是 OUTPUT；网站成品与单文件快照都不是任何正式构建的输入。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="从真源生成 current-status 文档")
    parser.add_argument("--check", action="store_true", help="门禁：与已提交内容逐字一致")
    args = parser.parse_args()
    content = render()
    if args.check:
        if not OUT.is_file():
            print(f"FAIL: {OUT} 不存在（先运行不带 --check 的生成）")
            return 1
        if OUT.read_text(encoding="utf-8") != content:
            print("FAIL: docs/current-status.md 与真源不符（重新生成并提交）")
            return 1
        print("current-status 门禁：与真源一致")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
