"""
数据导入服务（v17.9.10 统一版：fail-closed 校验 + 快照替换 + 生产三周期原子导入）

三条铁律：

1. fail-closed 校验（validate_snapshot）：导入前必须全部通过，否则零写入。
   - 同时接受 canonical 键 all_majors 与静态派生键 allMajors（唯一真源只有 canonical，
     静态键仅为部署存量兼容；两者 meta 约定不同，分别校验）
   - meta 必填：raw_total / excluded / total / recruits 全部存在且与行级守恒
     （canonical 约定 total=全行数、recruits=全行 sum(num)；
       静态约定 total=active 行数、recruits=active sum(num)——两种都必须自洽）
   - job_id 强格式 ^job-(\\d{4})-[0-9a-f]{20}$ 且年份与周期一致（不再"解析不了就放过"）
   - record_status 只允许已知值；排除行必须携带 exclusion_reason/evidence/excluded_at
   - 顶层 cycle 字段（若存在）必须与导入周期一致

2. snapshot replace（snapshot_replace）：快照是该周期的完整真像。
   - 行内字段 exact overwrite（源清空 → DB 清空，不做 `new or old` 残留）
   - 重新出现在 active 快照中的行 → 强制恢复 active（不继承历史 excluded）
   - DB 有但快照没有 → record_status='excluded'（保留审计痕迹，不物理删除）

3. 生产引导（import_all_data）：三周期（2024/2025/2026）+ 待遇 + 复核事件。
   - 全部文件先读取、先校验；任何一个缺失/校验失败 → 整体拒绝、零写入
   - 全部通过后单事务写入并一次性 commit
"""
import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.cycle import Cycle
from app.models.job import Job
from app.models.mirror_state import MirrorState
from app.models.review_event import ReviewEvent
from app.models.salary_data import SalaryData

JOB_ID_RE = re.compile(r"^job-(\d{4})-[0-9a-f]{20}$")
CYCLES: Tuple[str, ...] = ("2024", "2025", "2026")
_ACTIVE_STATUSES = {None, "", "active"}
_EXCLUDED_STATUSES = {"duplicate", "excluded"}
_VALID_RECORD_STATUS = _ACTIVE_STATUSES | _EXCLUDED_STATUSES


class SnapshotValidationError(Exception):
    """快照校验失败（fail-closed：调用方必须拒绝导入）"""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors[:5]) + (f"（共 {len(errors)} 条）" if len(errors) > 5 else ""))


def _extract_group(data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], list, Dict[str, Any]]:
    """兼容 canonical 键 all_majors 与静态派生键 allMajors，返回 (group, rows, meta)。"""
    group = data.get("all_majors")
    if not isinstance(group, dict):
        group = data.get("allMajors")
    if not isinstance(group, dict):
        return None, [], {}
    rows = group.get("rows")
    meta = group.get("meta")
    return group, rows if isinstance(rows, list) else [], meta if isinstance(meta, dict) else {}


def _to_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _row_active(row: Dict[str, Any]) -> bool:
    return row.get("record_status") in _ACTIVE_STATUSES


def _norm_record_status(value: Any) -> str:
    """DB 只存显式二值：active / excluded（canonical 的 None/duplicate 在此归一）。"""
    return "active" if value in _ACTIVE_STATUSES else "excluded"


def _job_id_set_sha256(job_ids: List[str]) -> str:
    """job_id 集合的确定性 SHA-256（与 canonical provenance 同算法：排序后按行拼接）"""
    blob = "\n".join(sorted(job_ids)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def validate_snapshot(cycle: str, data: Dict[str, Any], max_rows: int = 20000) -> List[str]:
    """校验快照数据，返回违规列表（空=通过）。纯函数，不修改任何状态。"""
    errors: List[str] = []
    group, rows, meta = _extract_group(data)

    if group is None:
        return ["缺少 all_majors/allMajors 数据组"]
    if not rows:
        return ["rows 缺失或为空——截断快照必须整体拒绝"]
    if len(rows) > max_rows:
        errors.append(f"rows 数量 {len(rows)} 超过上限 {max_rows}")

    doc_cycle = data.get("cycle")
    if doc_cycle is not None and str(doc_cycle) != cycle:
        errors.append(f"顶层 cycle={doc_cycle} 与导入周期 {cycle} 不一致")

    if not meta:
        errors.append("meta 缺失——无守恒锚点的快照必须整体拒绝")
        return errors

    # ---- 行级：job_id 强格式 + 周期一致 + 唯一 + num/record_status 合法 ----
    seen: Set[str] = set()
    active_rows = 0
    active_recruits = 0
    raw_recruits = 0
    excluded_rows = 0
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"rows[{i}] 不是对象")
            continue
        jid = row.get("job_id") or row.get("row_id")
        if not isinstance(jid, str) or not jid:
            errors.append(f"rows[{i}] 缺少 job_id")
            continue
        m = JOB_ID_RE.fullmatch(jid)
        if not m:
            errors.append(f"job_id 格式非法：{jid}（要求 job-{cycle}-<20位hex>）")
        elif m.group(1) != cycle:
            errors.append(f"job_id 周期不匹配：{jid}（期望 {cycle}）")
        if jid in seen:
            errors.append(f"job_id 重复：{jid}")
        seen.add(jid)

        num = _to_int(row.get("num"))
        if num is None or num < 0:
            errors.append(f"{jid}: num 非法（要求非负整数，实际 {row.get('num')!r}）")
            num = 0
        raw_recruits += num

        status = row.get("record_status")
        if status not in _VALID_RECORD_STATUS:
            errors.append(f"{jid}: record_status 非法：{status!r}")
        if _row_active(row):
            active_rows += 1
            active_recruits += num
        else:
            excluded_rows += 1
            for field in ("exclusion_reason", "exclusion_evidence", "excluded_at"):
                value = row.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"排除行 {jid} 缺 {field}")

    # ---- meta 守恒：全部必填，兼容 canonical（total=raw）与静态（total=active）约定 ----
    raw_total = _to_int(meta.get("raw_total"))
    if raw_total is None:
        errors.append("meta.raw_total 缺失")
    elif raw_total != len(rows):
        errors.append(f"meta.raw_total={raw_total} 与行数 {len(rows)} 不一致")

    meta_excluded = _to_int(meta.get("excluded"))
    if meta_excluded is None:
        errors.append("meta.excluded 缺失")
    elif meta_excluded != excluded_rows:
        errors.append(f"meta.excluded={meta_excluded} 与排除行数 {excluded_rows} 不一致")

    total = _to_int(meta.get("total"))
    if total is None:
        errors.append("meta.total 缺失")
    elif total not in (len(rows), active_rows):
        errors.append(f"meta.total={total} 既不等于全行数 {len(rows)} 也不等于 active 行数 {active_rows}")

    recruits = _to_int(meta.get("recruits"))
    if recruits is None:
        errors.append("meta.recruits 缺失")
    elif recruits not in (raw_recruits, active_recruits):
        errors.append(f"meta.recruits={recruits} 既不等于全行 sum(num)={raw_recruits} 也不等于 active sum(num)={active_recruits}")

    # ---- provenance 指纹（canonical 提供，静态无）：提供即必须匹配 ----
    provenance = data.get("provenance") or {}
    declared = provenance.get("job_id_set_sha256")
    if declared is not None:
        computed = _job_id_set_sha256([str(r.get("job_id") or r.get("row_id") or "") for r in rows if isinstance(r, dict)])
        if declared != computed:
            errors.append("provenance.job_id_set_sha256 与行集不一致")

    return errors


class ImportService:
    """数据导入服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def snapshot_replace(self, cycle: str, data: Dict[str, Any],
                               source_sha256: str = "",
                               release: str = "",
                               dry_run: bool = False) -> Dict[str, Any]:
        """快照替换导入。校验失败抛 SnapshotValidationError（零写入）。

        dry_run=True 只返回 would_* 统计，不修改 DB。
        """
        errors = validate_snapshot(cycle, data)
        if errors:
            raise SnapshotValidationError(errors)

        _, rows, meta = _extract_group(data)
        incoming_ids = {str(r.get("job_id") or r.get("row_id")) for r in rows}

        existing_result = await self.db.execute(select(Job).where(Job.cycle == cycle))
        existing_jobs = {j.job_id: j for j in existing_result.scalars().all()}
        existing_ids = set(existing_jobs.keys())

        stale_ids = existing_ids - incoming_ids
        new_ids = incoming_ids - existing_ids
        update_ids = incoming_ids & existing_ids

        if dry_run:
            return {
                "would_import": len(new_ids),
                "would_update": len(update_ids),
                "would_deactivate": len(stale_ids),
                "incoming_rows": len(rows),
                "existing_rows": len(existing_ids),
            }

        active_count = 0
        active_recruits = 0
        for row in rows:
            jid = str(row.get("job_id") or row.get("row_id"))
            job = existing_jobs.get(jid)
            if job is not None:
                self._full_update(job, row, cycle)
            else:
                self.db.add(self._create_job(row, cycle))
            if _row_active(row):
                active_count += 1
                active_recruits += int(row.get("num") or 0)

        # stale 下线（不物理删除，保留审计痕迹）
        for sid in stale_ids:
            existing_jobs[sid].record_status = "excluded"

        await self._update_cycle_meta(cycle, meta, active_count, active_recruits)

        job_id_hash = _job_id_set_sha256(list(incoming_ids))
        await self._upsert_mirror_state(
            cycle=cycle,
            release=release or str(data.get("label") or ""),
            source_sha256=source_sha256,
            job_id_set_sha256=job_id_hash,
            source_rows=len(rows),
            active_rows=active_count,
            recruits=active_recruits,
        )

        await self.db.flush()
        return {
            "imported": len(new_ids),
            "updated": len(update_ids),
            "deactivated": len(stale_ids),
            "active_rows": active_count,
            "incoming_rows": len(rows),
            "existing_rows": len(existing_ids),
            "job_id_set_sha256": job_id_hash,
        }

    def _create_job(self, row: Dict[str, Any], cycle: str) -> Job:
        return self._apply_row(Job(job_id=str(row.get("job_id") or row.get("row_id")), cycle=cycle), row, cycle)

    def _full_update(self, job: Job, row: Dict[str, Any], cycle: str) -> None:
        self._apply_row(job, row, cycle)

    def _apply_row(self, job: Job, row: Dict[str, Any], cycle: str) -> Job:
        """exact overwrite：源是什么就写什么（源清空 → DB 清空），绝不 `new or old` 残留。"""
        so = row.get("score_observation") or {}
        co = row.get("competition_observations") or {}
        metric_type = row.get("competition_metric_type")
        metric_obs = co.get(metric_type) if isinstance(metric_type, str) and metric_type else None
        metric_obs = metric_obs if isinstance(metric_obs, dict) else {}

        job.cycle = cycle
        job.code = row.get("code")
        job.city = row.get("city") or row.get("reg")
        job.exam = row.get("exam")
        job.unit = row.get("unit")
        job.zw = row.get("zw") or row.get("display_title")
        job.zy = row.get("zy")
        job.num = _to_int(row.get("num"))
        job.xl = row.get("xl")
        job.xw = row.get("xw")
        job.xz = row.get("xz")
        job.age = row.get("age")
        job.bz = row.get("bz")
        job.lb = row.get("lb") or row.get("dirText")
        job.bm = _to_int(row.get("bm"))
        job.title_status = row.get("title_status")
        job.display_title = row.get("display_title")
        job.job_status = row.get("job_status") or "active"
        # 重新出现在 active 快照 → 必须 active，绝不继承历史 excluded
        job.record_status = _norm_record_status(row.get("record_status"))
        job.score_observation_status = so.get("status")
        job.score_observation_scale_id = so.get("scale_id")
        job.score_observation_value = so.get("value")
        job.competition_metric_type = metric_type
        job.competition_base = _to_int(metric_obs.get("value"))
        job.competition_source = metric_obs.get("status")
        job.ratio_comparable = bool(row.get("ratio_comparable", False))
        job.source = row.get("source") or {}
        return job

    async def _update_cycle_meta(self, cycle: str, meta: Dict[str, Any],
                                 active_count: int, active_recruits: int) -> None:
        """周期元数据：用户口径存 active 数（与静态站一致）；raw 口径在 MirrorState。"""
        result = await self.db.execute(select(Cycle).where(Cycle.cycle == cycle))
        existing = result.scalar_one_or_none()
        score_unresolved = _to_int(meta.get("score_unresolved")) or 0
        if existing:
            existing.total_posts = active_count
            existing.total_recruits = active_recruits
            existing.score_unresolved = score_unresolved
        else:
            self.db.add(Cycle(
                cycle=cycle,
                label=f"{cycle}年度",
                total_posts=active_count,
                total_recruits=active_recruits,
                score_unresolved=score_unresolved,
                status="verified",
            ))

    async def _upsert_mirror_state(self, **kwargs: Any) -> None:
        result = await self.db.execute(select(MirrorState).where(MirrorState.cycle == kwargs["cycle"]))
        existing = result.scalar_one_or_none()
        if existing:
            for k, v in kwargs.items():
                if v is not None:
                    setattr(existing, k, v)
        else:
            self.db.add(MirrorState(**kwargs))

    async def import_salary_data(self, data: Dict[str, Any]) -> int:
        """导入待遇数据。data: {"series": {类型: {城市: {阶段: 值}}}, "stages": [...]}"""
        series = data.get("series") or {}
        stages = set(data.get("stages") or [])
        snapshot_year = str(data.get("snapshot") or "2026")

        count = 0
        for emp_type, cities in series.items():
            for city, values in cities.items():
                for stage, value in values.items():
                    if stages and stage not in stages:
                        continue
                    result = await self.db.execute(
                        select(SalaryData).where(
                            SalaryData.city == city,
                            SalaryData.employment_type == emp_type,
                            SalaryData.stage == stage,
                            SalaryData.snapshot_year == snapshot_year,
                        )
                    )
                    existing = result.scalar_one_or_none()
                    if existing:
                        existing.value_wan = value
                    else:
                        self.db.add(SalaryData(
                            city=city,
                            employment_type=emp_type,
                            stage=stage,
                            value_wan=value,
                            snapshot_year=snapshot_year,
                        ))
                    count += 1
        await self.db.flush()
        return count

    async def import_review_events(self, data: Dict[str, Any]) -> int:
        """导入复核事件。data: {"items": [...]}"""
        items = data.get("items") or []
        for item in items:
            self.db.add(ReviewEvent(
                kind=item.get("kind", "unknown"),
                severity=item.get("severity", "medium"),
                cycle=item.get("cycle"),
                title=item.get("title"),
                detail=item.get("detail"),
                evidence=item.get("evidence"),
                occurrences=item.get("occurrences", 1),
                resolution_trigger=item.get("resolution_trigger"),
                status="open",
            ))
        await self.db.flush()
        return len(items)


def _load_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def import_all_data(db: AsyncSession, data_path: Optional[str] = None) -> Dict[str, Any]:
    """生产引导导入（deploy.sh 调用，签名与 v17.9.8 保持兼容）。

    三周期 + 待遇 + 复核事件。任何文件缺失或任何快照校验失败 → 整体拒绝、零写入；
    全部通过后单事务写入，最后一次 commit。
    """
    if data_path is None:
        data_path = settings.STATIC_DATA_PATH

    # 阶段 1：全部读取 + 全部校验（fail-closed，任何问题零写入）
    prepared: List[Tuple[str, str, Dict[str, Any]]] = []
    missing: List[str] = []
    for cycle in CYCLES:
        path = os.path.join(data_path, "cycles", cycle, "jobs.json")
        if not os.path.exists(path):
            missing.append(path)
            continue
        prepared.append((cycle, path, _load_json_file(path)))
    if missing:
        raise RuntimeError(f"缺少周期数据文件（三周期缺一不可）: {', '.join(missing)}")

    for cycle, path, data in prepared:
        errors = validate_snapshot(cycle, data)
        if errors:
            raise SnapshotValidationError([f"{cycle}({os.path.basename(path)}): {e}" for e in errors])

    # 阶段 2：单事务写入
    service = ImportService(db)
    results: Dict[str, Any] = {}
    for cycle, path, data in prepared:
        with open(path, "rb") as f:
            source_sha256 = hashlib.sha256(f.read()).hexdigest()
        stats = await service.snapshot_replace(cycle, data, source_sha256=source_sha256)
        results[f"cycle_{cycle}"] = stats

    salary_path = os.path.join(data_path, "salary", "anhui.json")
    if os.path.exists(salary_path):
        count = await service.import_salary_data(_load_json_file(salary_path))
        results["salary"] = {"imported": count}

    review_path = os.path.join(data_path, "audit", "review-queue.json")
    if os.path.exists(review_path):
        count = await service.import_review_events(_load_json_file(review_path))
        results["review_events"] = {"imported": count}

    await db.commit()
    return results
