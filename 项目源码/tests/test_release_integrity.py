# -*- coding: utf-8 -*-
"""v17.8.6 发布完整性负向测试（fail-closed 证据链）。

覆盖：
  A. 锁纪律：sources.lock 篡改 → verify_sources 非零退出（不自动重签）；
     目录 rollup 新增文件 → 不匹配；缺源 → exit 2。
  B. canonical 损坏 7 例 → validate_canonical 全部拒绝（metrics 漂移、
     未知 record_status、排除证据被删、重复 job_id、score sha 错、
     raw_recruits 守恒破坏、job_id 周期前缀错）。
  C/D. staging 失败安全：暂存验证失败 → 生产零污染（自动回滚）；成功路径换入并留备份。
  E. git 干净预检：脏树拒绝；WANYU_DEV=1 + allow_dirty 豁免。
  F. 正式链纪律：永不重签锁（gen_sources_lock 零引用）、审计只读 --check、
     verify_sources 先于 build。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import verify_sources  # noqa: E402  项目源码/verify_sources.py（沙箱可 patch）
from tools.anhui_web import release_pipeline  # noqa: E402
from tools.anhui_web.release_pipeline import (  # noqa: E402
    BACKUP_SITE,
    PROD_SITE,
    promote_site,
)
from tools.anhui_web.validate_canonical import validate_cycle  # noqa: E402


# ---------------------------------------------------------------- A 锁纪律
class LockDisciplineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="wanyu-lockneg-"))
        self.patchers = [
            mock.patch.object(verify_sources, "ROOT", self.base),
            mock.patch.object(verify_sources, "LOCK_PATH", self.base / "项目源码" / "sources.lock.json"),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.addCleanup(self._teardown)

    def _teardown(self) -> None:
        for patcher in self.patchers:
            patcher.stop()
        shutil.rmtree(self.base, ignore_errors=True)

    def _main(self) -> int:
        # verify_sources.main() 内部 argparse 会吞掉 unittest 的 argv——显式给干净 argv。
        with mock.patch.object(sys, "argv", ["verify_sources.py"]):
            return verify_sources.main()

    def _seed(self) -> dict:
        file_path = self.base / "data" / "a.txt"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"hello")
        dir_path = self.base / "data" / "d"
        dir_path.mkdir(exist_ok=True)
        (dir_path / "1.txt").write_bytes(b"x")
        (dir_path / "2.txt").write_bytes(b"yy")
        digest, files, total = verify_sources.rollup(dir_path)
        return {
            "schema": "wanyu-source-lock/v2",
            "snapshot": "negative-test",
            "sources": [
                {"id": "f", "path": "data/a.txt", "sha256": verify_sources.sha256(file_path), "bytes": file_path.stat().st_size},
                {"id": "dir:d", "path": "data/d", "bytes": total, "files": files, "rollup_sha256": digest},
            ],
        }

    def _write_lock(self, lock: dict) -> None:
        (self.base / "项目源码").mkdir(exist_ok=True)
        (self.base / "项目源码" / "sources.lock.json").write_text(json.dumps(lock, ensure_ascii=False), encoding="utf-8")

    def test_consistent_lock_passes(self) -> None:
        self._write_lock(self._seed())
        self.assertEqual(self._main(), 0)

    def test_tampered_file_fails_without_relock(self) -> None:
        self._seed()
        lock = self._seed()  # regenerate lock from current state, then tamper
        self._write_lock(lock)
        (self.base / "data" / "a.txt").write_bytes(b"tampered")
        self.assertEqual(self._main(), 1)

    def test_new_file_breaks_dir_rollup(self) -> None:
        self._seed()
        self._write_lock(self._seed())
        (self.base / "data" / "d" / "3.txt").write_bytes(b"new")
        self.assertEqual(self._main(), 1)

    def test_missing_source_exits_2(self) -> None:
        self._seed()
        self._write_lock(self._seed())
        (self.base / "data" / "a.txt").unlink()
        self.assertEqual(self._main(), 2)


# ---------------------------------------------------------------- B canonical 损坏
class CanonicalCorruptionTests(unittest.TestCase):
    CYCLE = "2026"

    @classmethod
    def setUpClass(cls) -> None:
        cls.sandbox = Path(tempfile.mkdtemp(prefix="wanyu-canonneg-"))
        (cls.sandbox / "canonical").mkdir()
        shutil.copy(ROOT / "canonical" / "schema.json", cls.sandbox / "canonical" / "schema.json")
        (cls.sandbox / "canonical" / "cycles").mkdir()
        # 占位 score 文件：让 2026 的 sha 不匹配分支触发（真实文件 40MB，不入沙箱）
        score_dir = cls.sandbox / "tools" / "anhui_web" / "data"
        score_dir.mkdir(parents=True)
        (score_dir / "score_lists.json").write_bytes(b"placeholder-score-lists")
        cls.pristine: dict[str, bytes] = {}
        for cycle in ("2024", "2025", "2026"):
            raw = (ROOT / "canonical" / "cycles" / f"{cycle}.json").read_bytes()
            cls.pristine[cycle] = raw
            (cls.sandbox / "canonical" / "cycles" / f"{cycle}.json").write_bytes(raw)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.sandbox, ignore_errors=True)

    def _mutate(self, mutate) -> list[str]:
        cycle = self.CYCLE
        path = self.sandbox / "canonical" / "cycles" / f"{cycle}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        mutate(doc)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.addCleanup(lambda: path.write_bytes(self.pristine[cycle]))
        schema = json.loads((self.sandbox / "canonical" / "schema.json").read_text(encoding="utf-8"))
        return validate_cycle(self.sandbox, cycle, schema)["violations"]

    def _assert_violation(self, marker: str, mutate) -> None:
        violations = self._mutate(mutate)
        self.assertTrue(any(marker in v for v in violations), f"期望违规 [{marker}]，实际：{violations[:5]}")

    def _first_excluded(self, doc: dict) -> dict:
        return next(r for r in doc["all_majors"]["rows"] if r.get("record_status") not in (None, "active"))

    def test_metrics_drift_rejected(self) -> None:
        self._assert_violation("守恒失败 raw_posts", lambda d: d["metrics"].__setitem__("raw_posts", 8512))

    def test_unknown_record_status_rejected(self) -> None:
        self._assert_violation("schema 违规 @ all_majors.rows", lambda d: self._first_excluded(d).__setitem__("record_status", "ghost"))

    def test_missing_exclusion_evidence_rejected(self) -> None:
        self._assert_violation("缺证据字段 exclusion_evidence", lambda d: self._first_excluded(d).pop("exclusion_evidence"))

    def test_duplicate_job_id_rejected(self) -> None:
        def mutate(doc: dict) -> None:
            rows = doc["all_majors"]["rows"]
            rows[1]["job_id"] = rows[0]["job_id"]
        self._assert_violation("job_id 重复", mutate)

    def test_wrong_score_sha_rejected(self) -> None:
        self._assert_violation("score_state sha256", lambda d: d["score_state"].__setitem__("sha256", "0" * 64))

    def test_raw_recruits_conservation_rejected(self) -> None:
        self._assert_violation("守恒失败 raw_recruits", lambda d: d["metrics"].__setitem__("raw_recruits", d["metrics"]["raw_recruits"] + 1))

    def test_wrong_cycle_prefix_rejected(self) -> None:
        def mutate(doc: dict) -> None:
            row = doc["all_majors"]["rows"][0]
            row["job_id"] = "job-2025-" + row["job_id"].split("-", 2)[2]
        self._assert_violation("job_id 周期前缀不匹配", mutate)

    def test_real_tree_passes(self) -> None:
        import subprocess

        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "anhui_web" / "validate_canonical.py"), "--root", str(ROOT)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


# ---------------------------------------------------------------- C/D staging 失败安全
class PromoteSafetyTests(unittest.TestCase):
    def _prepare(self) -> tuple[Path, Path, Path]:
        base = Path(tempfile.mkdtemp(prefix="wanyu-promote-"))
        prod, backup, staging = base / "prod", base / "prod.previous", base / "staging"
        prod.mkdir()
        (prod / "index.html").write_text("PROD-ORIGINAL", encoding="utf-8")
        staging.mkdir()
        (staging / "index.html").write_text("STAGING-NEW", encoding="utf-8")
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        return prod, backup, staging

    def test_failed_staging_verify_leaves_production_untouched(self) -> None:
        prod, backup, staging = self._prepare()
        with mock.patch.object(release_pipeline, "PROD_SITE", prod), mock.patch.object(release_pipeline, "BACKUP_SITE", backup):
            def failing_verify(site: Path) -> None:
                raise RuntimeError("staging verification failed")
            with self.assertRaises(RuntimeError):
                promote_site(staging, failing_verify)
        self.assertEqual((prod / "index.html").read_text(encoding="utf-8"), "PROD-ORIGINAL")
        self.assertFalse(backup.exists(), "回滚后不得残留备份目录")

    def test_successful_promote_swaps_and_keeps_backup(self) -> None:
        prod, backup, staging = self._prepare()
        seen: list[Path] = []
        with mock.patch.object(release_pipeline, "PROD_SITE", prod), mock.patch.object(release_pipeline, "BACKUP_SITE", backup):
            promote_site(staging, lambda site: seen.append(site))
        self.assertEqual((prod / "index.html").read_text(encoding="utf-8"), "STAGING-NEW")
        self.assertEqual((backup / "index.html").read_text(encoding="utf-8"), "PROD-ORIGINAL")
        self.assertFalse(staging.exists())
        self.assertEqual(seen, [prod])

    def test_promote_refuses_when_production_missing(self) -> None:
        base = Path(tempfile.mkdtemp(prefix="wanyu-promote-missing-"))
        self.addCleanup(lambda: shutil.rmtree(base, ignore_errors=True))
        prod, backup, staging = base / "prod", base / "prod.previous", base / "staging"
        staging.mkdir()
        (staging / "index.html").write_text("STAGING-NEW", encoding="utf-8")
        with mock.patch.object(release_pipeline, "PROD_SITE", prod), mock.patch.object(release_pipeline, "BACKUP_SITE", backup):
            with self.assertRaises(RuntimeError):
                promote_site(staging, lambda site: None)
        self.assertTrue((staging / "index.html").exists(), "拒绝提升时 staging 不得被破坏")


# ---------------------------------------------------------------- E git 干净预检
class GitPrecheckTests(unittest.TestCase):
    def test_dirty_tree_rejected_without_dev_flag(self) -> None:
        marker = ROOT / ".wanyu-test-dirty.tmp"
        try:
            marker.write_text("dirty-marker", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                release_pipeline.git_precheck(allow_dirty=False)
            with mock.patch.dict(os.environ, {"WANYU_DEV": "1"}):
                self.assertTrue(release_pipeline.git_precheck(allow_dirty=True))
        finally:
            marker.unlink(missing_ok=True)

    def test_release_record_dir_is_pipeline_owned(self) -> None:
        # 发布资料/ 是流水线自产输出（本运行写入/重写），不得阻塞下一轮 precheck。
        self.assertTrue(release_pipeline._pipeline_owned('?? "发布资料/releases/v17.8.6/manifest.json"'))
        self.assertTrue(release_pipeline._pipeline_owned('?? 发布资料/'))
        self.assertFalse(release_pipeline._pipeline_owned(' M 项目源码/tools/anhui_web/release.py'))
        self.assertFalse(release_pipeline._pipeline_owned('?? "网站/data/site-manifest.json"'))

    def test_dirty_entries_exclude_release_record_dir(self) -> None:
        marker_dir = ROOT.parent / "发布资料" / ".wanyu-test-exempt"
        try:
            marker_dir.mkdir(parents=True, exist_ok=True)
            (marker_dir / "x.tmp").write_text("exempt", encoding="utf-8")
            dirty = [line for line in release_pipeline._dirty_entries() if not release_pipeline._pipeline_owned(line)]
            self.assertTrue(all("发布资料" not in line for line in dirty),
                            f"发布资料/ 未被 precheck 豁免：{[l for l in dirty if '发布资料' in l]}")
        finally:
            import shutil as _shutil

            _shutil.rmtree(marker_dir, ignore_errors=True)


# ---------------------------------------------------------------- F 正式链纪律（源码扫描）
class FormalChainDisciplineTests(unittest.TestCase):
    def test_formal_chain_never_relocks_sources(self) -> None:
        for name in ("release.py", "release_pipeline.py", "clean_rebuild.py"):
            source = (ROOT / "tools" / "anhui_web" / name).read_text(encoding="utf-8")
            self.assertNotIn("gen_sources_lock", source, f"{name} 不得引用锁重签工具（RB-02）")

    def test_audit_step_is_read_only_check(self) -> None:
        source = (ROOT / "tools" / "anhui_web" / "release_pipeline.py").read_text(encoding="utf-8")
        self.assertIn('"--check"', source, "正式链审计必须走 --check 只读复核")

    def test_verify_sources_runs_before_build(self) -> None:
        import inspect

        source = inspect.getsource(release_pipeline.run_pipeline)
        self.assertLess(source.index("verify_sources()"), source.index("build_site("), "锁校验必须先于构建")

    def test_legacy_suite_excluded_from_formal_list(self) -> None:
        release_source = (ROOT / "tools" / "anhui_web" / "release.py").read_text(encoding="utf-8")
        self.assertNotIn("tests.test_single_file_legacy", release_source, "遗留单文件套件不得进入正式测试清单")
        self.assertTrue((ROOT / "tests" / "test_single_file_legacy.py").is_file(), "遗留套件文件必须存在（重分类不等于删除）")

    def test_formal_module_list_covers_all_formal_suites(self) -> None:
        import re

        release_source = (ROOT / "tools" / "anhui_web" / "release.py").read_text(encoding="utf-8")
        listed = sorted(set(re.findall(r'"(tests\.test_[a-z0-9_]+)"', release_source)))
        on_disk = sorted(f"tests.{p.stem}" for p in (ROOT / "tests").glob("test_*.py"))
        expected = [m for m in on_disk if m != "tests.test_single_file_legacy"]
        self.assertEqual(listed, expected, f"正式清单与磁盘正式套件不一致；磁盘多出：{set(expected)-set(listed)} 清单多出：{set(listed)-set(expected)}")


if __name__ == "__main__":
    unittest.main()
