"""从三年统一构建载荷自动生成 ``docs/数据字典.md``。

数据字典必须直接读取与正式 HTML 相同的 bundle，避免只描述 2026 源 Word
或把旧版字段口径误写成当前交付口径。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.anhui_web import build_pages as builder  # noqa: E402
from tools.anhui_web.unified_cycle_bundle import build_unified_bundles  # noqa: E402

OUT = ROOT / "docs" / "数据字典.md"
CYCLES = ("2024", "2025", "2026")


def _read_audit() -> dict[str, Any]:
    path = ROOT / "tools" / "anhui_web" / "data" / "three_year_audit.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _value_present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _cycle_audit(audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("cycle")): item for item in audit.get("cycles", []) if isinstance(item, dict)}


def main() -> None:
    bundles = build_unified_bundles(ROOT)
    records_by_cycle = {cycle: list(bundles[cycle].records) for cycle in CYCLES}
    all_records = [record for cycle in CYCLES for record in records_by_cycle[cycle]]
    audit = _read_audit()
    audit_by_cycle = _cycle_audit(audit)

    field_coverage = Counter(
        field
        for record in all_records
        for field, value in record.items()
        if _value_present(value)
    )
    score_status_by_cycle: dict[str, Counter[str]] = {}
    competition_type_by_cycle: dict[str, Counter[str]] = {}
    title_status_by_cycle: dict[str, Counter[str]] = {}
    for cycle, records in records_by_cycle.items():
        score_status_by_cycle[cycle] = Counter(
            str((record.get("score_observation") or {}).get("status") or "unavailable")
            for record in records
        )
        competition_type_by_cycle[cycle] = Counter(
            str(record.get("competition_metric_type") or "unavailable")
            for record in records
        )
        title_status_by_cycle[cycle] = Counter(
            str(record.get("title_status") or "unavailable")
            for record in records
        )

    lines = [
        "# 皖域择岗档案 · 数据字典",
        "",
        f"构建版本 {builder.BUILD_VERSION} · 快照 {builder.DATA_SNAPSHOT} · 2024—2026 三周期 · 自动生成，勿手改。",
        "",
        "## 先读：真实性与完整性边界",
        "",
        "本字典描述正式 HTML 使用的三年统一 bundle。内部完整是指：已收集源包的岗位行、招录人数、字段结构、聚合结果和页面载荷可以复跑对账；它不等同于所有外部官方逐岗材料均已发布或取得。未发布、未取得或无法唯一匹配的值保持空值，并在审计与页面中显示状态，不转写成 0。",
        "",
        "- 三年审计报告：`docs/三年数据真实性与完整性审计_v12.md`；机器结果：`tools/anhui_web/data/three_year_audit.json`。",
        "- 正式入口：`deliverables/皖域择岗总览.html`；三个周期共用一个 HTML，通过周期切换读取对应 payload。",
        "- 证据状态：`verified`、`source_bundle`、`unpublished_or_unavailable`、`ambiguous_join`；具体含义以审计报告为准。",
        "",
        "## 三年岗位数据集",
        "",
        "| 周期 | 岗位行 | 招录人数 | 省考 | 事业编 | 国考 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cycle in CYCLES:
        records = records_by_cycle[cycle]
        exam_counts = Counter(str(record.get("exam") or "") for record in records)
        audit_cycle = audit_by_cycle.get(cycle, {})
        exams = audit_cycle.get("exams") or {}
        lines.append(
            f"| {cycle} | {len(records):,} | {sum(int(record.get('num') or 0) for record in records):,} | "
            f"{exam_counts.get('省考', 0):,} / {int((exams.get('省考') or {}).get('recruits') or 0):,} | "
            f"{exam_counts.get('事业编', 0):,} / {int((exams.get('事业编') or {}).get('recruits') or 0):,} | "
            f"{exam_counts.get('国考', 0):,} / {int((exams.get('国考') or {}).get('recruits') or 0):,} |"
        )
    lines += [
        "",
        f"合计：{len(all_records):,} 岗 / {sum(int(record.get('num') or 0) for record in all_records):,} 人。考试列为“岗位 / 招录人数”。",
        "",
        "### 行级身份、来源和展示字段",
        "",
        "| 字段 | 类型 | 覆盖行数 | 说明 |",
        "| --- | --- | ---: | --- |",
        f"| `job_id` | string | {field_coverage['job_id']:,} | 周期级稳定 ID；由 cycle、考试类别、城市、职位代码、单位和源表职位身份生成的 SHA-256 前缀，不含招录人数，人数修订不会换 ID。 |",
        f"| `row_id` | string | {field_coverage['row_id']:,} | v12.1 向后兼容的技术行 ID，当前与 `job_id` 对齐。 |",
        f"| `legacy_row_id` | string | {field_coverage['legacy_row_id']:,} | 仅在旧载荷存在时保留，用于迁移追溯；不作为新的收藏/对比主键。 |",
        f"| `city` / `exam` / `code` / `unit` / `num` | string / int | {min(field_coverage[field] for field in ('city', 'exam', 'code', 'unit', 'num')):,} | 城市、考试类别、职位代码、单位、招录人数；三年审计的必核主字段。 |",
        f"| `source_note` | string | {field_coverage['source_note']:,} | 行级来源提示；历史载荷缺少该字段时保持空值，不补写来源。 |",
        f"| `cycle` | string | {field_coverage['cycle']:,} | 所属周期；由统一 bundle 注入并用于周期级隔离。 |",
        f"| `title_status` / `display_title` | enum / string | {field_coverage['title_status']:,} / {field_coverage['display_title']:,} | 原表单列职位名称则为 `published`；未单列时显式显示“源表未单列披露”，不把单位名冒充职位名。 |",
        f"| `job_status` | enum | {field_coverage['job_status']:,} | `active` 或定向核除相关状态；原始核除行保留在档案层。 |",
        "",
        "### 成绩观测字段（禁止跨量纲比较）",
        "",
        "| 字段 | 类型 | 说明 |",
        "| --- | --- | --- |",
        f"| `score_observation` | object | {field_coverage['score_observation']:,} 行均有显式状态：`comparable`、`unavailable`、`suspected_sentinel`、`incompatible_scale` 或 `not_applicable`。 |",
        "| `score_observation.scale_id` | enum / null | 当前可比量纲：事业编合成分 `syb_300`、省考百分制 `province_100`；空值不得进入分数模拟。 |",
        "| `score_observation.value` | number / null | 原始入围线值；缺失保持 null，0 仅作为疑似哨兵值，不解释为真实成绩。 |",
        "",
        "### 竞争观测字段（报名人数与考试人数分开）",
        "",
        "| 字段 | 类型 | 说明 |",
        "| --- | --- | --- |",
        "| `competition_observations.registrations` | object | 报名/缴费阶段分母；数值 0 标记为 `suspected_sentinel`，不作为实测竞争人数。 |",
        "| `competition_observations.examinees` | object | 有效笔试/达线人数分母；与报名人数不相加、不混合。 |",
        "| `competition_metric_type` | enum / null | 逐行首选口径：`examinees`、`registrations`、国考 `interview_shortlisted` 或空值。 |",
        "| `ratio_comparable` | boolean | 仅在聚合分母类型单一且覆盖完整时为 true；混合分母、缺失分母、零哨兵或覆盖不完整时为 false，页面显示“不可比”。 |",
        "",
        "## 三年质量状态分布",
        "",
        "### 成绩状态",
        "",
        "| 周期 | 可比 | 未取得/缺失 | 疑似哨兵 | 量纲不兼容 | 不适用 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cycle in CYCLES:
        counter = score_status_by_cycle[cycle]
        lines.append(
            f"| {cycle} | {counter.get('comparable', 0):,} | {counter.get('unavailable', 0):,} | {counter.get('suspected_sentinel', 0):,} | "
            f"{counter.get('incompatible_scale', 0):,} | {counter.get('not_applicable', 0):,} |"
        )
    lines += [
        "",
        "### 竞争分母类型",
        "",
        "| 周期 | 考试人数 | 报名人数 | 国考进面名单 | 未取得/不可选 |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for cycle in CYCLES:
        counter = competition_type_by_cycle[cycle]
        lines.append(
            f"| {cycle} | {counter.get('examinees', 0):,} | {counter.get('registrations', 0):,} | {counter.get('interview_shortlisted', 0):,} | {counter.get('unavailable', 0):,} |"
        )
    lines += [
        "",
        "### 职位名称披露状态",
        "",
        "| 周期 | 源表单列 | 未单列披露 |",
        "| ---: | ---: | ---: |",
    ]
    for cycle in CYCLES:
        counter = title_status_by_cycle[cycle]
        lines.append(f"| {cycle} | {counter.get('published', 0):,} | {counter.get('not_separately_published', 0):,} |")

    lines += [
        "",
        "## 质量聚合字段",
        "",
        "- `jobs.cities[].competition_metrics`：按城市分别保存 `examinees`、`registrations`、`interview_shortlisted` 的 base / recruits / coverage_rows / ratio；不把不同观察类型叠加为一个分母。",
        "- `jobs.cities[].ratio_status`：`single_denominator`、`mixed_denominators`、`partial_coverage`、`unavailable`。只有 `single_denominator` 且 `ratio_comparable=true` 才允许排名、平替和推荐逻辑使用竞争比。",
        "- 2024/2025 的历史岗位聚合如果没有完整逐行分母，保留岗位数据但不生成虚假的城市竞争比；2026 的岗位观测台展示上述质量状态。",
        "",
        "## 成绩名单与安全关联",
        "",
        "| 周期 | `by_key` 岗位键 | 无法唯一匹配 |",
        "| ---: | ---: | ---: |",
    ]
    for cycle in CYCLES:
        coverage = (audit_by_cycle.get(cycle) or {}).get("coverage") or {}
        lines.append(f"| {cycle} | {int(coverage.get('score_by_key') or 0):,} | {int(coverage.get('score_unresolved') or 0):,} |")
    lines += [
        "",
        "成绩复合键为 `exam|city|code|recruits`。2026 成绩附件缺少城市且职位代码对应多个候选岗位的 116 条记录进入 `ambiguous_join`，不写入任一岗位；不能用代码单字段猜城市。",
        "",
        "## 待遇数据集",
        "",
        "- 身份 × 工龄：公务员 / 事业编 × 刚入职 / 1 年 / 3 年 / 5 年 / 10 年，共 160 个锚点。",
        "- 口径：年度全包估算中位数（应发 + 津补贴 + 公积金 + 年终等折算），为 2026 快照，不是政策工资、个人收入承诺或录用承诺。",
        "",
        "## 当前公开缺口",
        "",
    ]
    for cycle in CYCLES:
        gaps = (audit_by_cycle.get(cycle) or {}).get("gaps") or []
        lines.append(f"### {cycle}")
        lines.append("")
        if gaps:
            for gap in gaps:
                lines.append(f"- `{gap.get('kind', 'unknown')}` / `{gap.get('severity', '—')}`：{gap.get('title', '未命名缺口')}。证据：`{gap.get('evidence', '—')}`。")
        else:
            lines.append("- 当前审计清单未登记公开缺口。")
        lines.append("")
    lines += [
        "## JS 纯函数与交互安全边界",
        "",
        "- `score-metrics.js`：仅接受带 `score_observation` 且同一 `scale_id` 的可比成绩。",
        "- `product-core.js` / `product-jobs*.js`：竞争比消费统一经过 `competition_metric_type` 和 `ratio_comparable` 门禁；不同分母类型不用于平替或排名。",
        "- `cycle-runtime.js`：周期切换在同一 HTML 内重新挂载周期载荷，不强制 `location.reload()`；本地收藏、对比和备注按周期隔离。",
        "- `encodeShare / decodeShare`：本地状态分享码；不上传数据，不依赖网络。",
        "",
        "## 相关文件",
        "",
        "- 审计：`docs/三年数据真实性与完整性审计_v12.md`",
        "- 单文件反解析复核：`docs/三年单文件数据复核报告_v12.md`",
        "- 构建入口：`build.ps1`、`tools/anhui_web/release.py`",
        "- 质量实现：`tools/anhui_web/data_quality.py`、`tools/anhui_web/unified_cycle_bundle.py`",
        "- 页面校验：`tools/anhui_web/verify_single_file_v12.py`",
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("→", OUT)


if __name__ == "__main__":
    main()
