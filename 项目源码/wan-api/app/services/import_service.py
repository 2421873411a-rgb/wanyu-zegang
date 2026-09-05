"""
数据导入服务
从JSON文件导入数据到PostgreSQL
"""
import json
import os
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.job import Job
from app.models.cycle import Cycle
from app.models.score_index import ScoreIndex
from app.models.review_event import ReviewEvent
from app.models.salary_data import SalaryData
from app.config import settings


class ImportService:
    """数据导入服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def import_cycle_jobs(self, cycle: str, data: Dict[str, Any]) -> Dict[str, int]:
        """
        导入周期岗位数据
        data格式: {"allMajors": {"meta": {...}, "rows": [...]}}
        """
        stats = {"imported": 0, "updated": 0, "skipped": 0}
        
        rows = data.get("allMajors", {}).get("rows", [])
        meta = data.get("allMajors", {}).get("meta", {})
        
        for row in rows:
            job_id = row.get("job_id") or row.get("row_id")
            if not job_id:
                stats["skipped"] += 1
                continue
            
            # 检查是否已存在
            result = await self.db.execute(
                select(Job).where(Job.job_id == job_id)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # 更新现有记录
                self._update_job_from_row(existing, row, cycle)
                stats["updated"] += 1
            else:
                # 创建新记录
                job = self._create_job_from_row(row, cycle)
                self.db.add(job)
                stats["imported"] += 1
        
        # 更新周期元数据
        await self._update_cycle_meta(cycle, meta, len(rows))
        
        await self.db.flush()
        return stats
    
    def _create_job_from_row(self, row: Dict[str, Any], cycle: str) -> Job:
        """从行数据创建Job对象"""
        return Job(
            job_id=row.get("job_id") or row.get("row_id"),
            cycle=cycle,
            code=row.get("code"),
            city=row.get("city"),
            exam=row.get("exam"),
            unit=row.get("unit"),
            zw=row.get("zw") or row.get("display_title"),
            zy=row.get("zy"),
            num=row.get("num"),
            xl=row.get("xl"),
            xw=row.get("xw"),
            xz=row.get("xz"),
            age=row.get("age"),
            bz=row.get("bz"),
            lb=row.get("lb"),
            title_status=row.get("title_status"),
            display_title=row.get("display_title"),
            score_observation_status=row.get("score_observation", {}).get("status"),
            score_observation_value=row.get("score_observation", {}).get("value"),
            competition_metric_type=row.get("competition_observations", {}).get("metric_type"),
            competition_base=row.get("competition_observations", {}).get("base"),
            competition_source=row.get("competition_observations", {}).get("source"),
            ratio_comparable=row.get("ratio_comparable", False),
            source=row.get("source", {})
        )
    
    def _update_job_from_row(self, job: Job, row: Dict[str, Any], cycle: str):
        """更新Job对象"""
        job.code = row.get("code") or job.code
        job.city = row.get("city") or job.city
        job.exam = row.get("exam") or job.exam
        job.unit = row.get("unit") or job.unit
        job.zw = row.get("zw") or row.get("display_title") or job.zw
        job.zy = row.get("zy") or job.zy
        job.num = row.get("num") or job.num
        job.xl = row.get("xl") or job.xl
        job.xw = row.get("xw") or job.xw
        job.age = row.get("age") or job.age
        job.bz = row.get("bz") or job.bz
        job.lb = row.get("lb") or job.lb
    
    async def _update_cycle_meta(self, cycle: str, meta: Dict[str, Any], row_count: int):
        """更新周期元数据"""
        result = await self.db.execute(
            select(Cycle).where(Cycle.cycle == cycle)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.total_posts = meta.get("total", row_count)
            existing.total_recruits = meta.get("recruits", 0)
            existing.score_unresolved = meta.get("score_unresolved", 0)
        else:
            cycle_obj = Cycle(
                cycle=cycle,
                label=f"{cycle}年度",
                total_posts=meta.get("total", row_count),
                total_recruits=meta.get("recruits", 0),
                score_unresolved=meta.get("score_unresolved", 0),
                status="verified"
            )
            self.db.add(cycle_obj)
    
    async def import_salary_data(self, data: Dict[str, Any]) -> int:
        """
        导入待遇数据
        data格式: {"series": {"公务员": {...}, "事业编": {...}}, "stages": [...]}
        """
        series = data.get("series", {})
        stages = data.get("stages", [])
        snapshot_year = data.get("snapshot", "2026")
        
        count = 0
        for emp_type, cities in series.items():
            for city, values in cities.items():
                for stage, value in values.items():
                    if stage not in stages:
                        continue
                    
                    # 检查是否已存在
                    result = await self.db.execute(
                        select(SalaryData).where(
                            SalaryData.city == city,
                            SalaryData.employment_type == emp_type,
                            SalaryData.stage == stage,
                            SalaryData.snapshot_year == snapshot_year
                        )
                    )
                    existing = result.scalar_one_or_none()
                    
                    if existing:
                        existing.value_wan = value
                    else:
                        salary = SalaryData(
                            city=city,
                            employment_type=emp_type,
                            stage=stage,
                            value_wan=value,
                            snapshot_year=snapshot_year
                        )
                        self.db.add(salary)
                    count += 1
        
        await self.db.flush()
        return count
    
    async def import_review_events(self, data: Dict[str, Any]) -> int:
        """
        导入复核事件数据
        data格式: {"items": [...], "summary": {...}}
        """
        items = data.get("items", [])
        count = 0
        
        for item in items:
            event = ReviewEvent(
                kind=item.get("kind", "unknown"),
                severity=item.get("severity", "medium"),
                cycle=item.get("cycle"),
                title=item.get("title"),
                detail=item.get("detail"),
                evidence=item.get("evidence"),
                occurrences=item.get("occurrences", 1),
                resolution_trigger=item.get("resolution_trigger"),
                status="open"
            )
            self.db.add(event)
            count += 1
        
        await self.db.flush()
        return count


async def load_json_file(file_path: str) -> Dict[str, Any]:
    """加载JSON文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


async def import_all_data(db: AsyncSession, data_path: str = None):
    """
    导入所有数据
    data_path: 数据目录路径，默认使用配置中的STATIC_DATA_PATH
    """
    if data_path is None:
        data_path = settings.STATIC_DATA_PATH
    
    service = ImportService(db)
    results = {}
    
    # 导入周期数据
    cycles_dir = os.path.join(data_path, "cycles")
    if os.path.exists(cycles_dir):
        for cycle_name in ["2024", "2025", "2026"]:
            jobs_file = os.path.join(cycles_dir, cycle_name, "jobs.json")
            if os.path.exists(jobs_file):
                data = await load_json_file(jobs_file)
                stats = await service.import_cycle_jobs(cycle_name, data)
                results[f"cycle_{cycle_name}"] = stats
    
    # 导入待遇数据
    salary_file = os.path.join(data_path, "salary", "anhui.json")
    if os.path.exists(salary_file):
        data = await load_json_file(salary_file)
        count = await service.import_salary_data(data)
        results["salary"] = {"imported": count}
    
    # 导入复核事件
    review_file = os.path.join(data_path, "audit", "review-queue.json")
    if os.path.exists(review_file):
        data = await load_json_file(review_file)
        count = await service.import_review_events(data)
        results["review_events"] = {"imported": count}
    
    await db.commit()
    return results
