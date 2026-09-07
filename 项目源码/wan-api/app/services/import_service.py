"""Canonical/静态产物到数据库镜像的导入服务。"""
import json
import os
from typing import Any, Dict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.cycle import Cycle
from app.models.job import Job
from app.models.review_event import ReviewEvent
from app.models.salary_data import SalaryData


class ImportService:
    """岗位表是源数据镜像，不是第二真源。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _group(data: Dict[str, Any]) -> Dict[str, Any]:
        group = data.get("allMajors") or data.get("all_majors") or {}
        return group if isinstance(group, dict) else {}

    async def import_cycle_jobs(self, cycle: str, data: Dict[str, Any]) -> Dict[str, int]:
        """按周期做完整快照同步：全字段覆盖 + 删除源中已不存在的岗位。"""
        stats = {"imported": 0, "updated": 0, "skipped": 0, "deleted": 0}
        group = self._group(data)
        rows = group.get("rows") or []
        meta = group.get("meta") or {}
        incoming_ids: set[str] = set()

        for row in rows:
            if not isinstance(row, dict):
                stats["skipped"] += 1
                continue
            job_id = row.get("job_id") or row.get("row_id")
            if not job_id:
                stats["skipped"] += 1
                continue
            incoming_ids.add(str(job_id))

            result = await self.db.execute(select(Job).where(Job.job_id == job_id))
            job = result.scalar_one_or_none()
            if job is None:
                job = Job(job_id=str(job_id), cycle=cycle)
                self.db.add(job)
                stats["imported"] += 1
            else:
                stats["updated"] += 1
            self._apply_job(job, row, cycle)

        # 镜像语义：同一周期中不再出现在快照里的岗位必须移除。
        existing_ids = set((await self.db.execute(
            select(Job.job_id).where(Job.cycle == cycle)
        )).scalars().all())
        stale = existing_ids - incoming_ids
        if stale:
            await self.db.execute(delete(Job).where(Job.cycle == cycle, Job.job_id.in_(stale)))
            stats["deleted"] = len(stale)

        await self._update_cycle_meta(cycle, meta, len(rows))
        await self.db.flush()
        return stats

    @staticmethod
    def _apply_job(job: Job, row: Dict[str, Any], cycle: str) -> None:
        score = row.get("score_observation") if isinstance(row.get("score_observation"), dict) else {}
        competition = row.get("competition_observations") if isinstance(row.get("competition_observations"), dict) else {}
        source = row.get("source") if isinstance(row.get("source"), (dict, list)) else {}

        job.cycle = cycle
        job.code = row.get("code")
        job.city = row.get("city")
        job.exam = row.get("exam")
        job.unit = row.get("unit")
        job.zw = row.get("zw") or row.get("display_title")
        job.zy = row.get("zy")
        job.num = row.get("num")
        job.xl = row.get("xl")
        job.xw = row.get("xw")
        job.xz = row.get("xz")
        job.age = row.get("age")
        job.bz = row.get("bz")
        job.lb = row.get("lb")
        job.title_status = row.get("title_status")
        job.display_title = row.get("display_title")
        job.job_status = row.get("record_status") or row.get("job_status") or "active"
        job.score_observation_status = score.get("status")
        job.score_observation_scale_id = score.get("scale_id")
        job.score_observation_value = score.get("value")
        job.competition_metric_type = competition.get("metric_type")
        job.competition_base = competition.get("base")
        job.competition_source = competition.get("source")
        job.ratio_comparable = bool(row.get("ratio_comparable", False))
        job.source = source

    async def _update_cycle_meta(self, cycle: str, meta: Dict[str, Any], row_count: int) -> None:
        result = await self.db.execute(select(Cycle).where(Cycle.cycle == cycle))
        existing = result.scalar_one_or_none()
        if existing:
            existing.total_posts = meta.get("total", meta.get("active_total", row_count))
            existing.total_recruits = meta.get("recruits", 0)
            existing.score_unresolved = meta.get("score_unresolved", 0)
        else:
            self.db.add(Cycle(
                cycle=cycle,
                label=f"{cycle}年度",
                total_posts=meta.get("total", meta.get("active_total", row_count)),
                total_recruits=meta.get("recruits", 0),
                score_unresolved=meta.get("score_unresolved", 0),
                status="verified",
            ))

    async def import_salary_data(self, data: Dict[str, Any]) -> int:
        series = data.get("series", {})
        stages = data.get("stages", [])
        snapshot_year = data.get("snapshot", "2026")
        count = 0
        for emp_type, cities in series.items():
            for city, values in cities.items():
                for stage, value in values.items():
                    if stage not in stages:
                        continue
                    result = await self.db.execute(select(SalaryData).where(
                        SalaryData.city == city,
                        SalaryData.employment_type == emp_type,
                        SalaryData.stage == stage,
                        SalaryData.snapshot_year == snapshot_year,
                    ))
                    existing = result.scalar_one_or_none()
                    if existing:
                        existing.value_wan = value
                    else:
                        self.db.add(SalaryData(
                            city=city, employment_type=emp_type, stage=stage,
                            value_wan=value, snapshot_year=snapshot_year,
                        ))
                    count += 1
        await self.db.flush()
        return count

    async def import_review_events(self, data: Dict[str, Any]) -> int:
        items = data.get("items", [])
        count = 0
        for item in items:
            self.db.add(ReviewEvent(
                kind=item.get("kind", "unknown"), severity=item.get("severity", "medium"),
                cycle=item.get("cycle"), title=item.get("title"), detail=item.get("detail"),
                evidence=item.get("evidence"), occurrences=item.get("occurrences", 1),
                resolution_trigger=item.get("resolution_trigger"), status="open",
            ))
            count += 1
        await self.db.flush()
        return count


async def load_json_file(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def import_all_data(db: AsyncSession, data_path: str | None = None):
    data_path = data_path or settings.STATIC_DATA_PATH
    service = ImportService(db)
    results = {}
    cycles_dir = os.path.join(data_path, "cycles")
    if os.path.exists(cycles_dir):
        for cycle_name in ["2024", "2025", "2026"]:
            jobs_file = os.path.join(cycles_dir, cycle_name, "jobs.json")
            if os.path.exists(jobs_file):
                results[f"cycle_{cycle_name}"] = await service.import_cycle_jobs(
                    cycle_name, await load_json_file(jobs_file)
                )
    salary_file = os.path.join(data_path, "salary", "anhui.json")
    if os.path.exists(salary_file):
        results["salary"] = {"imported": await service.import_salary_data(await load_json_file(salary_file))}
    review_file = os.path.join(data_path, "audit", "review-queue.json")
    if os.path.exists(review_file):
        results["review_events"] = {"imported": await service.import_review_events(await load_json_file(review_file))}
    await db.commit()
    return results
