# -*- coding: utf-8 -*-
"""v17.8.6 阶段 E：clean rebuild——锁只读、零自签、零审计重写。

= 共享流水线（release_pipeline.py）的非提升形态：run_pipeline(promote=False)。
RB-02 修复：sources.lock 在发布/重建期间是【只读输入】，任何一步都不得重签；
three_year_audit.json 同为受锁工件，正式链禁止重生成——重生成只属于
--legacy-single-file 遗留链。

事实闸（2026）：raw 8511 = active 8401 + excluded 110；raw_recruits 12006 / recruits 11883；
lite/catalog/positions/major_city = 8401；score_unresolved=0 / resolved=116。
任何一步失败 → 非 0 退出，禁止发布。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from tools.anhui_web.release_pipeline import EXPECTED_2026, run_pipeline  # noqa: E402


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="wanyu-clean-rebuild-"))
    print(f"clean rebuild = 流水线（promote=False）→ {out_dir}")
    run_pipeline(out_dir, promote=False, allow_dirty=True, tests_summary={"status": "not-run-in-clean-rebuild"})
    print("2026 锁定事实：", EXPECTED_2026)
    print("注意：tmp 产物与 网站 的字节差异仅允许来自 runtime source_file（canonical 引用名）等装配元数据；")
    print("如需同步生产，请执行发布流水线（release.py：staging → 原子提升）而非手工拷贝。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
