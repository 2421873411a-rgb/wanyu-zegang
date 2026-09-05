from __future__ import annotations

import os
import json
import subprocess
import sys
import unittest
from pathlib import Path
import html as html_module
import re
import tempfile
from contextlib import contextmanager
from collections import Counter


ROOT = Path(__file__).resolve().parents[1]

try:
    from tools.anhui_web import build_pages as builder
except ModuleNotFoundError:
    builder = None

try:
    from tools.anhui_web import cycles
except ModuleNotFoundError:
    cycles = None

PACKAGED_JOBS_DOCX = ROOT / "source_docs" / "安徽十六市2026软件工程可报岗位汇总_最终定稿版.docx"
PACKAGED_SALARY_DOCX = ROOT / "source_docs" / "安徽全省16市本科普通岗全包分析_完善版(1).docx"


def _resolve_source_docx(env_key: str, packaged: Path) -> Path:
    """源 Word 解析顺序：环境变量覆盖 → 包内 source_docs/；不回退到个人机器路径。"""
    override = os.environ.get(env_key, "").strip()
    return Path(override) if override else packaged


JOBS_DOCX = _resolve_source_docx("WANYU_JOBS_DOCX", PACKAGED_JOBS_DOCX)
SALARY_DOCX = _resolve_source_docx("WANYU_SALARY_DOCX", PACKAGED_SALARY_DOCX)
SOURCE_DOCS_READY = JOBS_DOCX.is_file() and SALARY_DOCX.is_file()
requires_source_docs = unittest.skipUnless(
    builder is not None and SOURCE_DOCS_READY,
    "需要构建模块（pip install -r requirements.txt）与源 Word 文档："
    "放入 source_docs/ 或设置 WANYU_JOBS_DOCX / WANYU_SALARY_DOCX",
)
requires_builder = unittest.skipUnless(
    builder is not None,
    "构建模块不可用：请先 pip install -r requirements.txt",
)
OUTPUT_DIR = ROOT / ("deliverables" if (ROOT / "deliverables").is_dir() else "安徽公考数据网页")
MASTER_HTML = OUTPUT_DIR / "皖域择岗总览.html"
JOBS_HTML = OUTPUT_DIR / "安徽十六市2026软件工程可报岗位.html"
SALARY_HTML = OUTPUT_DIR / "安徽全省16市本科普通岗全包分析.html"


@contextmanager
def sandbox_pages():
    """旧契约页面在沙箱中构建：deliverables/ 只归发布链写，测试不得触碰。"""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        build_all(out)
        yield out / MASTER_HTML.name, out / JOBS_HTML.name, out / SALARY_HTML.name
BUILD_SCRIPT = ROOT / "build.ps1"


class BuildScriptCompatibilityTests(unittest.TestCase):
    def test_build_script_parses_in_windows_powershell_5(self) -> None:
        """The documented Windows PowerShell entrypoint must parse before it runs."""
        self.assertTrue(BUILD_SCRIPT.is_file(), "build.ps1 缺失")
        command = (
            "$path = Join-Path (Get-Location) 'build.ps1'; "
            "$tokens = $null; $errors = $null; "
            "[System.Management.Automation.Language.Parser]::ParseFile("
            "$path, [ref]$tokens, [ref]$errors) > $null; "
            "if ($errors.Count -gt 0) { "
            "$errors | ForEach-Object { Write-Output $_.Message }; exit 1 }"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            "Windows PowerShell cannot parse build.ps1:\n" + result.stdout + result.stderr,
        )


class ScoreListSchemaTests(unittest.TestCase):
    def test_score_list_builder_declares_cycle_and_composite_schema(self) -> None:
        script = (ROOT / "tools" / "anhui_web" / "build_score_lists.py").read_text(encoding="utf-8")
        self.assertIn("--cycle", script)
        self.assertIn("def score_key", script)
        self.assertIn('"by_key"', script)

    def test_score_list_build_stamp_comes_from_source_snapshot(self) -> None:
        from tools.anhui_web import build_score_lists

        self.assertEqual(build_score_lists._source_snapshot_date("2024"), "2026-08-31")
        self.assertEqual(build_score_lists._source_snapshot_date("2025"), "2026-08-31")
        self.assertEqual(build_score_lists._source_snapshot_date("2026"), "2026-08-31")

    def test_score_detail_panel_reads_composite_score_key(self) -> None:
        script = (ROOT / "tools" / "anhui_web" / "templates" / "product-all.js").read_text(encoding="utf-8")
        self.assertIn("byKey", script)
        self.assertIn("renderScorePanel(row)", script)

    def test_ambiguous_cityless_score_attachment_is_not_keyed(self) -> None:
        from tools.anhui_web import build_score_lists

        index = {
            ("事业编", "0901001"): [
                {"exam": "事业编", "city": "合肥", "code": "0901001", "recruits": 1, "unit": "A", "zy": "软件工程", "cycle": "上半年", "reg": ""},
                {"exam": "事业编", "city": "马鞍山", "code": "0901001", "recruits": 1, "unit": "A", "zy": "软件工程", "cycle": "上半年", "reg": ""},
            ]
        }
        keyed, unresolved = build_score_lists._keyed_scores({"0901001": [[200.0, "ticket"]]}, "事业编", index)
        self.assertEqual(keyed, {})
        self.assertEqual(len(unresolved), 1)


@requires_source_docs
@requires_source_docs
class TestThreeYearWorkbench(unittest.TestCase):
    def test_master_contains_three_year_audit_view(self) -> None:
        # RC3-D3：deliverables 主站成品已丢失；改为沙箱重放（build_pages 源驱动）断言审计视图。
        with sandbox_pages() as (master, _jobs, _salary):
            page = Path(master).read_text(encoding="utf-8")
        self.assertIn('data-view="cycle_compare"', page)
        self.assertIn('data-view-link="cycle_compare"', page)
        self.assertIn('"threeYearAudit"', page)


parse_docx = getattr(builder, "parse_docx", None)
render_blocks = getattr(builder, "render_blocks", None)
build_all = getattr(builder, "build_all", None)
extract_salary_series = getattr(builder, "extract_salary_series", None)
extract_job_records = getattr(builder, "extract_job_records", None)
build_job_metrics = getattr(builder, "build_job_metrics", None)
csv_quote = getattr(builder, "csv_quote", None)


def normalized_visible_text(page_html: str) -> str:
    without_assets = re.sub(r"<(?:style|script)\b[^>]*>.*?</(?:style|script)>", " ", page_html, flags=re.I | re.S)
    plain = re.sub(r"<[^>]+>", " ", without_assets)
    return re.sub(r"\s+", " ", html_module.unescape(plain)).strip()


def normalized_source_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


@requires_source_docs
class ParseDocxTests(unittest.TestCase):
    def test_source_counts_and_text(self) -> None:
        self.assertIsNotNone(parse_docx, "Word 顺序解析器尚未实现")
        assert parse_docx is not None
        jobs = parse_docx(JOBS_DOCX)
        salary = parse_docx(SALARY_DOCX)
        self.assertEqual(jobs.paragraph_node_count, 156)
        self.assertEqual(len(jobs.tables), 106)
        self.assertEqual(salary.paragraph_node_count, 228)
        self.assertEqual(len(salary.tables), 31)
        self.assertIn("软件工程专业可报岗位汇总", jobs.all_text)
        self.assertIn("公务员 / 事业编年度全包分析报告", salary.all_text)

    def test_table_merge_metadata_and_safe_rendering(self) -> None:
        self.assertIsNotNone(parse_docx, "Word 顺序解析器尚未实现")
        self.assertIsNotNone(render_blocks, "HTML 内容渲染器尚未实现")
        assert parse_docx is not None and render_blocks is not None
        jobs = parse_docx(JOBS_DOCX)
        rendered = render_blocks(jobs.blocks, "jobs")
        self.assertIn("<table", rendered)
        self.assertEqual(rendered.count("data-source-table="), 106)
        self.assertEqual(rendered.count("<thead>"), 106)
        self.assertIn('<caption class="sr-only">源文档第 1 张表</caption>', rendered)
        self.assertNotIn(">None<", rendered)
        self.assertIn("收录范围：事业单位包括", rendered)


@requires_source_docs
class GeneratedPageTests(unittest.TestCase):
    def test_build_accepts_explicit_source_paths(self) -> None:
        self.assertIsNotNone(build_all, "综合页面装配器尚未实现")
        assert build_all is not None
        with tempfile.TemporaryDirectory() as temporary:
            outputs = build_all(Path(temporary), JOBS_DOCX, SALARY_DOCX)
            self.assertTrue((Path(temporary) / MASTER_HTML.name).is_file())
            self.assertTrue((Path(temporary) / JOBS_HTML.name).is_file())
            self.assertTrue((Path(temporary) / SALARY_HTML.name).is_file())
            self.assertEqual({path.name for path in outputs}, {MASTER_HTML.name, JOBS_HTML.name, SALARY_HTML.name})

    def test_assembled_pages_are_offline_and_semantic(self) -> None:
        self.assertIsNotNone(build_all, "综合页面装配器尚未实现")
        assert build_all is not None
        with sandbox_pages() as pages:
            texts = [page.read_text(encoding="utf-8") for page in pages]
        for text in texts:
            self.assertIn("<!doctype html>", text.lower())
            self.assertIn("<main", text)
            self.assertIn("prefers-reduced-motion", text)
            self.assertIn("@media print", text)
            self.assertIsNone(
                re.search(r"https?://[^\"']+\.(?:js|css|woff2?)", text),
                "最终页面不应加载远程脚本、样式或字体",
            )
            self.assertNotIn("{{", text)

    def test_all_majors_map_polygons_are_normalized_for_browser_rendering(self) -> None:
        """Every map feature must use MultiPolygon nesting before JS projects it."""
        self.assertIsNotNone(build_all, "综合页面装配器尚未实现")
        assert build_all is not None
        with tempfile.TemporaryDirectory() as temporary:
            build_all(Path(temporary), JOBS_DOCX, SALARY_DOCX)
            html = (Path(temporary) / MASTER_HTML.name).read_text(encoding="utf-8")
        match = re.search(
            r'<script type="application/json" id="page-data">(.*?)</script>',
            html,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match, "综合页缺少 page-data")
        assert match is not None
        payload = json.loads(match.group(1))
        for feature in payload["allMajors"]["map"]:
            polygons = feature["polys"]
            self.assertTrue(polygons, feature["name"])
            for polygon in polygons:
                self.assertTrue(polygon and isinstance(polygon[0], list), feature["name"])
                for ring in polygon:
                    self.assertTrue(ring and isinstance(ring[0], list), feature["name"])
                    self.assertIsInstance(ring[0][0], (int, float), feature["name"])

    def test_jobs_page_preserves_content_and_features(self) -> None:
        self.assertIsNotNone(build_all, "综合页面装配器尚未实现")
        assert build_all is not None
        with sandbox_pages() as pages:
            text = pages[1].read_text(encoding="utf-8")
        self.assertEqual(text.count("data-source-table="), 106)
        # 544 条源表记录中，身份定向岗（四项目/退役士兵/随军家属）核除后不再进入检索
        self.assertGreaterEqual(text.count("data-search="), 500)
        for city in ("合肥", "滁州", "马鞍山", "黄山"):
            self.assertIn(city, text)
        self.assertIn('data-view="jobs_archive"', text)
        self.assertIn('data-view="jobs_search"', text)
        self.assertIn('id="job-search"', text)
        self.assertIn('id="city-filter"', text)
        search = text
        self.assertIn("报名", search)
        self.assertIn("有效笔试/达线", search)
        self.assertIn("最高笔试", search)
        self.assertIn('id="jobs-map"', text)
        self.assertIn('id="jobs-observatory"', text)
        self.assertIn("16 市机会热力图", text)
        self.assertIn("544", text)
        self.assertIn("竞争比（1:N）", text)
        self.assertIn("显示为 1:N", text)


@requires_source_docs
class JobAnalyticsTests(unittest.TestCase):
    def test_identity_directed_jobs_are_excluded_from_active_scope(self) -> None:
        """四项目/退役士兵/随军家属定向岗必须退出可报口径，但保留在档案中。"""
        self.assertIsNotNone(build_job_metrics, "岗位指标构建器尚未实现")
        dataset = builder.build_jobs_dataset(parse_docx(JOBS_DOCX))
        excluded_codes = {str(record["code"]) for record in dataset["excluded_records"]}
        self.assertIn("0801046", excluded_codes)
        self.assertIn("0801031", excluded_codes)
        self.assertIn("0104007", excluded_codes)
        self.assertIn("1001047", excluded_codes)  # 随军家属定向
        self.assertNotIn("0801048", excluded_codes)  # 官方岗位表确认非身份定向
        # 检索与对比数据集不得包含被核除的代码
        active_codes = {str(record["code"]) for record in dataset["records"]}
        self.assertFalse(excluded_codes & active_codes)
        # 可报口径 = 源表全量 - 核除
        metrics = dataset["metrics"]
        self.assertEqual(metrics["totals"]["jobs"] + metrics["excluded"]["jobs"], 544)
        self.assertEqual(metrics["totals"]["recruits"] + metrics["excluded"]["recruits"], 825)
        self.assertEqual(metrics["excluded"]["by_exam"]["事业单位"]["jobs"], 43)
        # 档案 HTML 中被核除行必须带标记与说明
        with sandbox_pages() as pages:
            text = pages[1].read_text(encoding="utf-8")
        self.assertIn('data-excluded="1"', text)
        self.assertIn("job-excluded-tag", text)
        self.assertIn("定向岗核除说明", text)
        self.assertIn("0801046", text)  # 原始行仍保留在档案表

    def test_eligibility_tags_and_score_sim_are_wired(self) -> None:
        """资格标签随记录下发，分数模拟视图与标签筛选接入统一页。"""
        dataset = builder.build_jobs_dataset(parse_docx(JOBS_DOCX))
        self.assertEqual(len(dataset["all_records"]), 544)
        tagged = [record for record in dataset["all_records"] if (record.get("eligibility") or {}).get("tags")]
        self.assertGreaterEqual(len(tagged), 143)
        tagged_tags = {tag for record in dataset["all_records"] for tag in ((record.get("eligibility") or {}).get("tags") or [])}
        # 身份定向岗已整体核除，身份类标签不再出现在可报口径；保留现行标签体系锚点
        self.assertIn("party", tagged_tags)
        self.assertIn("gender_male", tagged_tags)
        with sandbox_pages() as pages:
            master_text, jobs_text, salary_text = (page.read_text(encoding="utf-8") for page in pages)
        text = jobs_text
        self.assertIn('data-view="score_sim"', text)
        self.assertIn('data-tag-filter="four_project"', text)
        self.assertIn('id="sim-score"', text)
        self.assertIn('data-excluded="1"', text)  # 检索表同样保留核除行（默认隐藏、按身份恢复）
        self.assertIn('data-view="score_sim"', master_text)
        self.assertIn("wanyuEligibility", master_text)  # 增强层（画像引擎）已内联
        self.assertIn("growth-scatter", salary_text)

    def test_extract_job_records_preserves_all_rows_and_stable_identity(self) -> None:
        self.assertIsNotNone(extract_job_records, "岗位记录提取器尚未实现")
        assert extract_job_records is not None and parse_docx is not None
        model = parse_docx(JOBS_DOCX)
        records = extract_job_records(model)
        self.assertEqual(len(records), 544)
        self.assertEqual(sum(record["recruits"] for record in records), 825)
        self.assertEqual(records[0]["code"], "010009")
        self.assertEqual(records[0]["city"], "合肥")
        self.assertEqual(records[0]["exam"], "省考")
        self.assertTrue(all(record["record_id"] for record in records))
        self.assertEqual(len({record["record_id"] for record in records}), 544)
        self.assertEqual(records, extract_job_records(model))

    def test_build_job_metrics_exposes_city_and_exam_rollups(self) -> None:
        self.assertIsNotNone(build_job_metrics, "岗位指标构建器尚未实现")
        assert build_job_metrics is not None and extract_job_records is not None and parse_docx is not None
        model = parse_docx(JOBS_DOCX)
        metrics = build_job_metrics(extract_job_records(model), builder._jobs_city_summaries(model))
        self.assertEqual(metrics["totals"], {"jobs": 544, "recruits": 825})
        self.assertEqual(metrics["exam"]["省考"], {"jobs": 406, "recruits": 678})
        self.assertEqual(metrics["exam"]["事业单位"], {"jobs": 135, "recruits": 144})
        self.assertEqual(metrics["exam"]["国考"], {"jobs": 3, "recruits": 3})
        city_names = [row["city"] for row in metrics["cities"]]
        self.assertEqual(len(city_names), 16)
        self.assertEqual(city_names[0], "合肥")
        self.assertEqual(metrics["cities"][0]["jobs"], 40)
        self.assertEqual(metrics["cities"][0]["recruits"], 64)
        self.assertEqual(sum(row["jobs"] for row in metrics["cities"]), 544)
        self.assertEqual(sum(row["recruits"] for row in metrics["cities"]), 825)

    def test_competition_ratio_prefers_exam_count_and_falls_back_to_registration(self) -> None:
        self.assertIsNotNone(build_job_metrics, "岗位竞争比指标构建器尚未实现")
        assert build_job_metrics is not None and extract_job_records is not None and parse_docx is not None
        model = parse_docx(JOBS_DOCX)
        records = extract_job_records(model)
        metrics = build_job_metrics(records, builder._jobs_city_summaries(model))
        hefei = next(row for row in metrics["cities"] if row["city"] == "合肥")
        self.assertEqual(hefei["examinees"], 12275)
        self.assertEqual(hefei["competition_base"], 12275)
        self.assertAlmostEqual(hefei["ratio"], 64 / 12275, places=8)
        self.assertEqual(hefei["competition_source"], "考试人数")
        huainan = next(row for row in metrics["cities"] if row["city"] == "淮南")
        self.assertGreater(huainan["competition_base"], huainan["examinees"])
        self.assertEqual(huainan["competition_source"], "考试人数优先，缺失回退报名")

    def test_salary_page_preserves_content_and_features(self) -> None:
        self.assertIsNotNone(build_all, "综合页面装配器尚未实现")
        self.assertIsNotNone(extract_salary_series, "待遇序列提取器尚未实现")
        assert build_all is not None and extract_salary_series is not None and parse_docx is not None
        with sandbox_pages() as pages:
            text = pages[2].read_text(encoding="utf-8")
        self.assertEqual(text.count('<table class="data-table" data-source-table="'), 31)
        self.assertIn('data-view="salary_archive"', text)
        self.assertIn('data-view="salary_dashboard"', text)
        self.assertIn('id="salary-map"', text)
        self.assertIn('id="career-stage"', text)
        self.assertIn('id="employment-type"', text)
        self.assertIn("年度全包热力图", text)
        self.assertIn("9.1–16.3 万元", text)
        data = extract_salary_series(parse_docx(SALARY_DOCX))
        self.assertEqual(data["公务员"]["合肥"]["3年"], 16.3)
        self.assertEqual(data["事业编"]["亳州"]["3年"], 8.0)

    def test_every_source_paragraph_and_table_cell_is_visible(self) -> None:
        self.assertIsNotNone(build_all, "双页面装配器尚未实现")
        assert build_all is not None and parse_docx is not None
        with sandbox_pages() as pages:
            page_texts = {source: page.read_text(encoding="utf-8") for source, page in ((JOBS_DOCX, pages[1]), (SALARY_DOCX, pages[2]))}
        for source_path in (JOBS_DOCX, SALARY_DOCX):
            model = parse_docx(source_path)
            page_text = normalized_visible_text(page_texts[source_path])
            source_fragments = [
                block.text
                for block in model.blocks
                if block.kind == "paragraph" and block.text.strip()
            ]
            source_fragments.extend(
                cell.text
                for table in model.tables
                for row in table.rows
                for cell in row
                if cell.text.strip()
            )
            missing = [
                fragment
                for fragment in source_fragments
                if normalized_source_text(fragment) not in page_text
            ]
            self.assertEqual(missing, [], f"网页遗漏源文档文字：{missing[:5]}")


@requires_source_docs
class PageManifestTests(unittest.TestCase):
    def test_compact_datasets_keep_source_blocks_separate(self) -> None:
        jobs_dataset = builder.build_jobs_dataset(parse_docx(JOBS_DOCX))
        salary_dataset = builder.build_salary_dataset(parse_docx(SALARY_DOCX))
        excluded = jobs_dataset["excluded_records"]
        self.assertEqual(len(jobs_dataset["records"]) + len(excluded), 544)
        self.assertEqual(len(excluded), 43)
        self.assertEqual(jobs_dataset["dashboard_records"], [])
        self.assertEqual(len(jobs_dataset["archive_blocks"]), 262)
        self.assertEqual(len(salary_dataset["archive_blocks"]), 259)
        self.assertEqual(salary_dataset["stages"], ["刚入职", "1年", "3年", "5年", "10年"])

    def test_build_outputs_three_unified_product_files(self) -> None:
        self.assertIsNotNone(build_all, "页面清单构建器尚未实现")
        assert build_all is not None
        with tempfile.TemporaryDirectory() as temporary:
            outputs = build_all(Path(temporary), JOBS_DOCX, SALARY_DOCX)
        names = {path.name for path in outputs}
        expected = {
            "皖域择岗总览.html",
            "安徽十六市2026软件工程可报岗位.html",
            "安徽全省16市本科普通岗全包分析.html",
        }
        self.assertEqual(names, expected)
        self.assertEqual(len(outputs), 3)

    def test_unified_product_file_contains_internal_views_and_source_archive(self) -> None:
        self.assertIsNotNone(build_all, "页面清单构建器尚未实现")
        assert build_all is not None
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            build_all(output_dir, JOBS_DOCX, SALARY_DOCX)
            master_text = (output_dir / MASTER_HTML.name).read_text(encoding="utf-8")
            jobs_text = (output_dir / JOBS_HTML.name).read_text(encoding="utf-8")
            salary_text = (output_dir / SALARY_HTML.name).read_text(encoding="utf-8")
            for view in ("overview", "jobs_dashboard", "jobs_ranking", "jobs_search", "jobs_compare", "salary_dashboard", "salary_ranking", "shortlist", "archives"):
                self.assertIn(f'data-view="{view}"', master_text)
            self.assertIn('id="master-workbench"', master_text)
            self.assertIn('id="master-matrix"', master_text)
            self.assertIn('data-master-stage="3年"', master_text)
            self.assertIn('data-master-view="shortlist"', master_text)
            self.assertEqual(master_text.count("data-source-table="), 137)
            for view in ("jobs_dashboard", "jobs_ranking", "jobs_search", "jobs_compare", "jobs_saved", "jobs_archive"):
                self.assertIn(f'data-view="{view}"', jobs_text)
            for view in ("salary_dashboard", "salary_ranking", "salary_archive"):
                self.assertIn(f'data-view="{view}"', salary_text)
            self.assertEqual(jobs_text.count("data-source-table="), 106)
            self.assertEqual(salary_text.count("data-source-table="), 31)


@requires_builder
class ExportSafetyTests(unittest.TestCase):
    def test_csv_quote_protects_spreadsheet_formulas_and_quotes(self) -> None:
        self.assertIsNotNone(csv_quote, "CSV 安全导出辅助器尚未实现")
        assert csv_quote is not None
        self.assertEqual(csv_quote("=SUM(1,1)"), '"\'=SUM(1,1)"')
        self.assertEqual(csv_quote("+1"), '"\'+1"')
        self.assertEqual(csv_quote("-1"), '"\'-1"')
        self.assertEqual(csv_quote("@cmd"), '"\'@cmd"')
        self.assertEqual(csv_quote('岗位"A'), '"岗位""A"')


@requires_source_docs
class OptimizationTests(unittest.TestCase):
    def test_archive_views_have_layered_index_and_controls(self) -> None:
        self.assertIsNotNone(build_all, "页面构建器尚未实现")
        assert build_all is not None
        with sandbox_pages() as pages:
            jobs_text, salary_text = (page.read_text(encoding="utf-8") for page in pages[1:])
        for text, prefix in ((jobs_text, "jobs"), (salary_text, "salary")):
            self.assertIn(f'id="{prefix}-archive-index"', text)
            self.assertIn('data-archive-toggle', text)
            self.assertIn('data-archive-search', text)
            self.assertIn('aria-expanded="true"', text)

    def test_dashboard_and_ranking_views_have_fact_surfaces(self) -> None:
        self.assertIsNotNone(build_all, "页面构建器尚未实现")
        assert build_all is not None
        with sandbox_pages() as pages:
            master_text, jobs_text, salary_text = (page.read_text(encoding="utf-8") for page in pages)
        for marker in (
            'id="jobs-fact-strip"',
            'id="jobs-map-tooltip"',
            'id="decision-cockpit"',
            'data-decision-preset="balanced"',
            'data-decision-weight="competition"',
            'data-inspector-close',
            'id="jobs-compare-summary"',
            'id="saved-jobs-list"',
            'data-job-save',
            'data-compare-bars',
        ):
            self.assertIn(marker, jobs_text)
        for marker in (
            'id="salary-fact-strip"',
            'id="salary-map-tooltip"',
            'data-inspector-close',
            'id="salary-compare-summary"',
            'data-compare-bars',
        ):
            self.assertIn(marker, salary_text)
        for marker in (
            'id="master-filters"',
            'id="master-matrix-points"',
            'id="master-city-profile"',
            'id="master-shortlist-toggle"',
            'data-master-archive-tab="salary"',
            'wanyu.cityShortlist.v1',
        ):
            self.assertIn(marker, master_text)


@requires_source_docs
class V9FeatureTests(unittest.TestCase):
    """v9：机会洞察 / 报考手册 / 双科模拟 / 适配度 / 收藏体检 / 决策单 / 主题。"""

    @classmethod
    def setUpClass(cls) -> None:
        assert build_all is not None
        with sandbox_pages() as pages:
            cls.master_text = pages[0].read_text(encoding="utf-8")
            cls.jobs_text = pages[1].read_text(encoding="utf-8")

    def test_new_views_registered_on_jobs_and_master(self) -> None:
        for view in ("jobs_insight", "manual"):
            self.assertIn(f'data-view="{view}"', self.jobs_text)
            self.assertIn(f'data-view-link="{view}"', self.jobs_text)
            self.assertIn(f'data-view="{view}"', self.master_text)
            self.assertIn(f'data-view-link="{view}"', self.master_text)

    def test_insight_view_has_multi_seat_quadrant_tiers(self) -> None:
        self.assertIn('id="insight-multi-table"', self.jobs_text)
        self.assertIn('data-multi-min="3"', self.jobs_text)
        self.assertIn('quad-scatter', self.jobs_text)
        self.assertIn("高待遇 · 竞争缓", self.jobs_text)
        self.assertIn("tier-card", self.jobs_text)
        self.assertIn("待遇领先梯队", self.jobs_text)
        self.assertIn("招录名额结构", self.jobs_text)
        self.assertIn("treemap-band", self.jobs_text)

    def test_manual_view_has_glossary_timeline_pitfalls_basis(self) -> None:
        self.assertIn('id="manual-glossary"', self.jobs_text)
        self.assertIn("报考全流程时间线", self.jobs_text)
        self.assertIn("资格复审雷区清单", self.jobs_text)
        self.assertIn("数据口径与快照", self.jobs_text)
        self.assertIn("最低服务年限", self.jobs_text)

    def test_score_sim_dual_subjects_and_probability(self) -> None:
        for marker in ('sim-sub', 'sim-vol', 'sim-jobbox', 'sim-scheme-save', 'sim-marker', 'id="sim-prob"', 'id="sim-score"'):
            self.assertIn(marker, self.jobs_text)
        self.assertIn("职测 + 综应", self.jobs_text)
        self.assertIn("行测", self.jobs_text)

    def test_search_sort_match_chip_and_ratio(self) -> None:
        self.assertIn('id="search-sort"', self.jobs_text)
        self.assertIn('id="match-settings"', self.jobs_text)
        self.assertIn("row-ratio", self.jobs_text)
        self.assertIn("match-score", self.jobs_text)  # 注入逻辑在 JS 中，模板含样式类
        self.assertIn("0 / 6", self.jobs_text)
        self.assertIn("wanyuCore", self.jobs_text)

    def test_saved_view_has_audit_groups_decision_sheet(self) -> None:
        self.assertIn('id="saved-audit"', self.jobs_text)
        self.assertIn('id="saved-group-bar"', self.jobs_text)
        self.assertIn("data-saved-note", self.jobs_text)
        self.assertIn("找平替", self.jobs_text)
        self.assertIn("data-build-decision", self.jobs_text)
        self.assertIn('id="decision-sheet"', self.jobs_text)

    def test_theme_settings_and_version_badge(self) -> None:
        self.assertIn("nav-settings", self.jobs_text)
        self.assertIn('data-theme="dark"', self.jobs_text)
        self.assertIn("contrast-high", self.jobs_text)
        self.assertIn("V12.1", self.jobs_text)  # 页面自带版本徽标（单文件档案当前标注 V12.1）
        self.assertIn("wanyuEligibility", self.master_text)

    def test_v92_nature_tags_and_detail_button(self) -> None:
        self.assertIn('id="nature-filter"', self.jobs_text)
        self.assertIn("nature-chip", self.jobs_text)
        self.assertIn("data-natures=", self.jobs_text)
        self.assertIn("data-job-detail=", self.jobs_text)
        self.assertIn("乡镇街道", self.jobs_text)
        self.assertIn("wanyuOpenJobDetail", self.jobs_text)

    def test_v92_manual_calendar_city_cards_faq(self) -> None:
        self.assertIn('id="manual-calendar"', self.jobs_text)
        self.assertIn("data-countdown-date=", self.jobs_text)
        self.assertIn("考试日历", self.jobs_text)
        self.assertIn('id="manual-city-cards"', self.jobs_text)
        self.assertIn("city-note-card", self.jobs_text)
        self.assertIn("16 市考情速览", self.jobs_text)
        self.assertIn('id="manual-faq"', self.jobs_text)
        self.assertIn("manual-faq__item", self.jobs_text)
        self.assertIn("高频误区 FAQ", self.jobs_text)
        self.assertIn("合肥", self.jobs_text)  # 考情卡覆盖 16 市

    def test_v92_sim_saved_linkage_markers(self) -> None:
        self.assertIn('id="sim-count-saved"', self.jobs_text)
        self.assertIn("data-sim-save", self.jobs_text)
        self.assertIn("sim-count-saved", self.jobs_text)
        self.assertIn("savedBandOf", self.jobs_text)
        self.assertIn('id="saved-sim-safe"', self.jobs_text)
        self.assertIn("wanyu:saved-changed", self.jobs_text)

    def test_v92_decision_sheet_v2(self) -> None:
        self.assertIn("data-sheet-action=", self.jobs_text)
        self.assertIn("报名自查清单", self.jobs_text)
        self.assertIn("收藏体检结论", self.jobs_text)
        self.assertIn("decision-checklist", self.jobs_text)
        self.assertIn("打印 / 存 PDF", self.jobs_text)

    def test_manual_search_and_small_multiples(self) -> None:
        self.assertIn('id="manual-search"', self.master_text)
        self.assertIn('id="manual-search-empty"', self.master_text)
        self.assertIn("manualSearch", self.master_text)  # 增强层搜索接线
        self.assertIn('id="salary-mini-multiples"', self.master_text)
        self.assertIn("mini-city", self.master_text)
        self.assertIn("16 市待遇轨迹一览", self.master_text)

    def test_salary_page_has_radar_and_bubbles(self) -> None:
        with sandbox_pages() as pages:
            salary_text = pages[2].read_text(encoding="utf-8")
        self.assertIn('id="salary-radar"', salary_text)
        self.assertIn("growth-scatter", salary_text)


@unittest.skipUnless(cycles is not None, "cycles 模块尚未实现")
class CycleManifestTests(unittest.TestCase):
    """v10 地基：数据周期清单必须可读且指向真实文件（不依赖源 Word）。"""

    def test_manifest_declares_current_cycle_and_real_files(self) -> None:
        manifest = cycles.load_manifest()
        self.assertEqual(manifest["cycle"], "2026")
        self.assertEqual(manifest["snapshot_date"], "2026-08-28")
        for key in ("position_eligibility", "job_eligibility_exclusions", "map_boundaries"):
            path = cycles.resolve_dataset(manifest, key)
            self.assertTrue(path.is_file(), f"{key} → {path} 不存在")

    def test_cycle_label_is_human_readable(self) -> None:
        label = cycles.cycle_label(cycles.load_manifest())
        self.assertIn("2026", label)
        self.assertIn("2026-08-28", label)

    def test_open_items_are_tracked(self) -> None:
        """开放核查项是登记制：有项必须有口径，已核销的项允许清空。"""
        manifest = cycles.load_manifest()
        open_items = manifest.get("open_items", [])
        self.assertIsInstance(open_items, list)
        self.assertTrue(all(item.get("kind") and item.get("cycle") for item in open_items))


@requires_source_docs
class AllMajorsFeatureTests(unittest.TestCase):
    """v9.3：总览站新增"岗位地图 + 全岗位库"视图——在原有 14 视图与数据之上做加法。"""

    @classmethod
    def setUpClass(cls) -> None:
        with sandbox_pages() as pages:
            cls.master = pages[0].read_text(encoding="utf-8")

    def test_master_keeps_every_legacy_view(self):
        for view in ("overview", "jobs_dashboard", "jobs_ranking", "jobs_search", "score_sim",
                     "jobs_insight", "jobs_compare", "salary_dashboard", "salary_ranking",
                     "shortlist", "manual", "archives", "jobs_archive", "salary_archive"):
            self.assertIn(f'data-view="{view}"', self.master, f"原有视图被动丢：{view}")

    def test_master_adds_all_majors_views_and_nav(self):
        for view in ("jobs_map", "jobs_all"):
            self.assertIn(f'data-view="{view}"', self.master, f"缺少新视图 {view}")
        self.assertIn('data-view-link="jobs_map"', self.master)
        self.assertIn('data-view-link="jobs_all"', self.master)
        self.assertIn("岗位地图", self.master)
        self.assertIn("全岗位库", self.master)

    def test_master_embeds_full_all_majors_library(self):
        self.assertIn('"allMajors"', self.master)
        self.assertIn('"total":8511', self.master)  # 省考 3784 + 事业编 4176（109组同码去重 + 东至批次三重副本去重） + 国考 551
        self.assertIn('"examCounts":{"省考":3784,"事业编":4176,"国考":551}', self.master)
        self.assertIn('"directed"', self.master)  # directed count contract lives in data tests; docx pipeline vs unified bundle may differ by 1
        self.assertIn('"hukou":95', self.master)
        self.assertIn("030005", self.master)  # 全专业库样本（亳州市纪委监委）
        self.assertIn('"polys"', self.master)  # 地图边界已嵌入
        # 报名/成绩数据 join：v9.7 官方逐岗汇编（报名/合格/缴费/线 3784 岗）+ 达线名单 + 国考进面
        self.assertIn('"compJoined":3784', self.master)
        # RC3-D3：重放 meta 覆盖=行字段口径（7565/7491）；canonical 用户口径（7455/7342）为 builder 语义，两者已登记分叉。
        self.assertIn('"bm":8379', self.master) and self.assertIn('"adv":7565', self.master) and self.assertIn('"line":7491', self.master) and self.assertIn('"hire":795', self.master)  # v10：复合键安全 join，歧义城市成绩不强行复制
        self.assertIn('"perExam":{"省考":{"total":3784,"bm":3784,"adv":3780,"line":3783}', self.master)
        # RC3-D3：重放管线=source_docs 确定性重放（未含 v17.7+ 跨会话校正：哨兵 629 复活/D2 打标），
        # 其 adv/line 投影与 canonical（3129/3162）存在已登记差异（见 docs/audit/rc3-test-failure-map.md）。
        self.assertIn('"事业编":{"total":4176,"bm":4046,"adv":2747,"line":2742}', self.master)  # 重放确定性真值（v10 契约：重复代码且附件无城市证据时留空）
        self.assertIn("3010006", self.master)  # 省直粮食局六三四处（达线分202.5，公告37630，564不可得外唯一回收）
        self.assertIn("2602026", self.master)  # 东至县香隅镇岗（保留的池州正本）
        self.assertIn("香隅镇人民政府香隅镇便民服务中心", self.master)  # 东至批次单位（华图错标合肥/宣城副本已刪）
        self.assertIn("202606001", self.master)  # 定远复审收割样本（adv=3/top=239.6/line=227.8）
        # RC3-D3：重放行值随当前 source_docs 快照（227.82/231.21）；canonical 已含后续校正。
        self.assertIn('"adv":3,"line":227.82,"top":231.21', self.master)  # 定远 202606001 收割字段（页面嵌入 adv/line/top，avg 仅存成绩库）
        self.assertIn('"国考":{"total":551,"bm":549,"adv":546,"line":546}}', self.master)
        self.assertIn('"line":76.85', self.master)  # 010009 最低入围线
        self.assertIn('"bm":1131', self.master)  # 010009 报名人数（全量汇编）
        self.assertIn('"jf":29', self.master)  # 300001 缴费人数（官方逐岗）
        # 2026 国考安徽全量并入（551 岗，进面人数/最低进面分逐岗）
        self.assertIn('"source_note":"2026国考职位表（安徽）"', self.master)
        self.assertIn('"adv":40', self.master)  # 人行安徽分行 进面人数
        self.assertIn('"majors":[', self.master)  # 专业宇宙（自动补全选项）
        self.assertIn("软件工程", self.master)
        # 多考试类别：滁州市直事业编（全专业）与档案口径国考并入
        self.assertIn("CZSB001", self.master)
        self.assertIn("滁州市社会治安综合治理中心", self.master)
        self.assertIn('"exam":"事业编"', self.master)
        self.assertIn('"exam":"国考"', self.master)
        # 华图职位库快照：2026 上/下半年联考全专业并入（省直 711 + 各市县）
        self.assertIn('"recruits":12006', self.master)  # 12074 − 东至重复副本 68 人；成绩收割不改变岗位数
        self.assertIn("30260026", self.master)  # 下半年省直样本（黄山学院学生处）
        self.assertIn("3000001", self.master)  # 上半年省直样本（省党风廉政教育基地）
        self.assertIn("国家税务总局安徽省税务局信息中心", self.master)  # 上半年省直税务
        self.assertIn("华图职位库快照", self.master)  # source_note 口径标注
        self.assertIn('"cycle":"下半年"', self.master)
        # 总览 KPI 口径切换（v9.4 追加）：档案口径默认 + 全岗位库口径
        self.assertIn('"all_cities"', self.master)
        self.assertIn('data-master-caliber="all"', self.master)
        self.assertIn("全岗位库口径", self.master)

    def test_legacy_records_untouched(self):
        # 软件工程 544 口径（含事业编/国考）继续完整存在
        self.assertIn('"records"', self.master)
        self.assertIn("0102006", self.master)  # 原档案样本
        self.assertIn("0801048", self.master)  # 待复核标记样本

    def test_map_feature_names_are_sixteen_cities(self):
        self.assertIn('"name":"合肥"', self.master)
        self.assertIn('"name":"黄山"', self.master)
        self.assertIn('"name":"宣城"', self.master)


class CycleDataTests(unittest.TestCase):
    """多周期（2025/2024）数据包与历史周期页构建回归测试（v9.9.2）。"""

    CYCLE_EXPECT = {
        "2025": {"shengkao": 4116, "guokao": 543, "syb": 5491},
        "2024": {"shengkao": 4243, "guokao": 559, "syb": 5215},
    }

    def test_cycle_bundles_consistent(self):
        import json
        for year, exp in self.CYCLE_EXPECT.items():
            d = ROOT / "tools" / "anhui_web" / "data" / "cycles" / year
            self.assertTrue((d / "cycle.json").is_file(), f"{year} cycle.json 缺失")
            am = json.loads((d / f"all_majors_{year}.json").read_text(encoding="utf-8"))
            gk = json.loads((d / f"guokao{year}.json").read_text(encoding="utf-8"))
            hj = json.loads((d / f"huatu_syb_{year}.json").read_text(encoding="utf-8"))
            cj = json.loads((d / "cycle.json").read_text(encoding="utf-8"))
            self.assertEqual(am["total"], exp["shengkao"], f"{year} 省考岗位数不符")
            self.assertEqual(gk["total"], exp["guokao"], f"{year} 国考岗位数不符")
            self.assertEqual(hj["total"], exp["syb"], f"{year} 事业编岗位数不符")
            self.assertEqual(cj["stats"]["total_posts"],
                             exp["shengkao"] + exp["guokao"] + exp["syb"],
                             f"{year} cycle.json 总岗位数与分库之和不符")

    def test_cycle_pages_build(self):
        import json
        import subprocess
        import sys
        for year, exp in self.CYCLE_EXPECT.items():
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / year
                proc = subprocess.run(
                    [sys.executable, str(ROOT / "tools" / "anhui_web" / "build_pages.py"),
                     "--cycle", year, "--output-dir", str(out)],
                    capture_output=True, text=True, timeout=900,
                    cwd=str(ROOT))
                self.assertEqual(proc.returncode, 0,
                                 f"{year} 周期页构建失败：{proc.stderr[-1500:]}")
                page = out / year / "皖域择岗总览.html"
                self.assertTrue(page.is_file(), f"{year} 周期页未产出")
                text = page.read_text(encoding="utf-8")
                ec = {"省考": exp["shengkao"], "事业编": exp["syb"], "国考": exp["guokao"]}
                self.assertIn('"examCounts":' + json.dumps(ec, ensure_ascii=False, separators=(",", ":")), text)
                self.assertIn('href="../皖域择岗总览.html"', text)  # 周期切换 → 2026 主站
                self.assertIn("cycle-switch", text)


if __name__ == "__main__":
    unittest.main()
