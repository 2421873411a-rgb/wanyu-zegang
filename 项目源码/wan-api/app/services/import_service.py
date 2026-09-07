"""
数据导入服务（v17.9.9：强校验 + 全字段覆盖 + 缺失行 deactivate + mirror state）

P1-1：快照导入前必须通过全部校验，否则数据库零写入：
  - job_id 格式校验（job-{cycle}-*）
  - job_id 周期一致性（job_id 中的 cycle 必须与 URL cycle 一致）
  - duplicate job_id 检测
  - meta metrics 守恒（raw_posts/recruits 与 rows 一致性）
  - canonical schema 基本校验（allMajors.rows 非空、meta 存在）

P1-2：snapshot replace（不是 partial upsert）：
  - 传入的 rows 是该周期的完整快照
  - DB 中该周期已有但快照中没有的行 → record_status='excluded'
  - 不会跨周期删除/修改

P1-3：全字段覆盖（_update_job_from_row 不再只更新部分字段）
"""
import hashlib
import re
from typing import Any, Dict, List, Set

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cycle import Cycle
from app.models.job import Job
from app.models.mirror_state import MirrorState


def _job_id_cycle(job_id: str) -> str:
    """从 job_id 提取周期：job-2026-xxx → '2026'"""
    m = re.match(r'^job-(\d{4})-', str(job_id or ''))
    return m.group(1) if m else ''


def _job_id_set_sha256(job_ids: List[str]) -> str:
    """计算 job_id 集合的确定性 SHA-256（排序后拼接）"""
    blob = '\n'.join(sorted(job_ids)).encode('utf-8')
    return hashlib.sha256(blob).hexdigest()


def validate_snapshot(cycle: str, data: Dict[str, Any], max_rows: int = 20000) -> List[str]:
    """校验快照数据，返回违规列表（空=通过）。不修改任何状态。"""
    errors: List[str] = []

    rows = (data.get('allMajors') or {}).get('rows')
    if not isinstance(rows, list) or not rows:
        errors.append('allMajors.rows 缺失或为空')
        return errors
    if len(rows) > max_rows:
        errors.append(f'rows 数量 {len(rows)} 超过上限 {max_rows}')

    meta = (data.get('allMajors') or {}).get('meta') or {}

    # job_id 格式 + 周期一致性 + 重复检测
    seen_ids: Set[str] = set()
    for i, row in enumerate(rows):
        jid = str(row.get('job_id') or row.get('row_id') or '')
        if not jid:
            errors.append(f'第 {i} 行缺少 job_id/row_id')
            continue
        id_cycle = _job_id_cycle(jid)
        if id_cycle and id_cycle != cycle:
            errors.append(f'job_id 周期不匹配：{jid}（期望 {cycle}，实际 {id_cycle}）')
        if jid in seen_ids:
            errors.append(f'duplicate job_id: {jid}')
        seen_ids.add(jid)

    # meta metrics 守恒
    meta_total = meta.get('total') or meta.get('raw_posts') or meta.get('raw_total')
    meta_recruits = meta.get('recruits')
    if meta_total is not None and int(meta_total) != len(rows):
        errors.append(f'meta.total={meta_total} 但实际 rows={len(rows)}')
    if meta_recruits is not None:
        actual_recruits = sum(int(r.get('num') or 0) for r in rows)
        if int(meta_recruits) != actual_recruits:
            errors.append(f'meta.recruits={meta_recruits} 但实际 sum(num)={actual_recruits}')

    return errors


class ImportService:
    """数据导入服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def snapshot_replace(self, cycle: str, data: Dict[str, Any],
                                source_sha256: str = '',
                                release: str = '',
                                dry_run: bool = False) -> Dict[str, Any]:
        """快照替换导入（P1-1/P1-2/P1-3）。

        校验通过后：DB 中该周期已有但快照中没有的行 → record_status='excluded'；
        快照中的行全字段写入（create 或全量 update）。
        dry_run=True 只返回 would_change 统计，不修改 DB。
        """
        rows = (data.get('allMajors') or {}).get('rows')
        meta = (data.get('allMajors') or {}).get('meta') or {}
        incoming_ids = {str(r.get('job_id') or r.get('row_id') or '') for r in rows}

        # 查询 DB 中该周期已有行
        existing_result = await self.db.execute(
            select(Job).where(Job.cycle == cycle)
        )
        existing_jobs = {j.job_id: j for j in existing_result.scalars().all()}
        existing_ids = set(existing_jobs.keys())

        stale_ids = existing_ids - incoming_ids  # DB 有但快照没有
        new_ids = incoming_ids - existing_ids     # 快照有但 DB 没有
        update_ids = incoming_ids & existing_ids  # 两边都有

        imported = len(new_ids)
        updated = len(update_ids)
        deactivated = len(stale_ids)

        if dry_run:
            return {
                'would_import': imported,
                'would_update': updated,
                'would_deactivate': deactivated,
                'incoming_rows': len(rows),
                'existing_rows': len(existing_ids),
            }

        # 写入：新行 + 全量更新
        for row in rows:
            jid = str(row.get('job_id') or row.get('row_id') or '')
            if not jid:
                continue
            if jid in existing_jobs:
                self._full_update(existing_jobs[jid], row, cycle)
            else:
                self.db.add(self._create_job(row, cycle))

        # deactivate stale（不物理删除，保留审计痕迹）
        for sid in stale_ids:
            if sid in existing_jobs:
                existing_jobs[sid].record_status = 'excluded'

        # 周期元数据
        await self._update_cycle_meta(cycle, meta, len(rows))

        # mirror state 持久化
        job_id_hash = _job_id_set_sha256(list(incoming_ids))
        actual_recruits = sum(int(r.get('num') or 0) for r in rows)
        await self._upsert_mirror_state(
            cycle=cycle,
            release=release,
            source_sha256=source_sha256,
            job_id_set_sha256=job_id_hash,
            source_rows=len(rows),
            active_rows=len(rows),
            recruits=actual_recruits,
        )

        await self.db.flush()

        return {
            'imported': imported,
            'updated': updated,
            'deactivated': deactivated,
            'incoming_rows': len(rows),
            'existing_rows': len(existing_ids),
            'job_id_set_sha256': job_id_hash,
        }

    def _create_job(self, row: Dict[str, Any], cycle: str) -> Job:
        """创建 Job（全字段）"""
        co = row.get('competition_observations') or {}
        so = row.get('score_observation') or {}
        return Job(
            job_id=row.get('job_id') or row.get('row_id'),
            cycle=cycle,
            code=row.get('code'),
            city=row.get('city') or row.get('reg'),
            exam=row.get('exam'),
            unit=row.get('unit'),
            zw=row.get('zw') or row.get('display_title'),
            zy=row.get('zy'),
            num=row.get('num'),
            xl=row.get('xl'),
            xw=row.get('xw'),
            xz=row.get('xz'),
            age=row.get('age'),
            bz=row.get('bz'),
            lb=row.get('lb'),
            bm=row.get('bm'),
            title_status=row.get('title_status'),
            display_title=row.get('display_title'),
            job_status=row.get('job_status', 'active'),
            record_status=row.get('record_status', 'active'),
            score_observation_status=so.get('status'),
            score_observation_value=so.get('value'),
            competition_metric_type=co.get('metric_type'),
            competition_base=co.get('base'),
            competition_source=co.get('source'),
            ratio_comparable=row.get('ratio_comparable', False),
            source=row.get('source', {}),
        )

    def _full_update(self, job: Job, row: Dict[str, Any], cycle: str):
        """全字段更新（P1-3：不再只更新部分字段）"""
        co = row.get('competition_observations') or {}
        so = row.get('score_observation') or {}
        job.cycle = cycle
        job.code = row.get('code') or job.code
        job.city = row.get('city') or row.get('reg') or job.city
        job.exam = row.get('exam') or job.exam
        job.unit = row.get('unit') or job.unit
        job.zw = row.get('zw') or row.get('display_title') or job.zw
        job.zy = row.get('zy') or job.zy
        job.num = row.get('num') if row.get('num') is not None else job.num
        job.xl = row.get('xl') or job.xl
        job.xw = row.get('xw') or job.xw
        job.xz = row.get('xz') or job.xz
        job.age = row.get('age') or job.age
        job.bz = row.get('bz') or job.bz
        job.lb = row.get('lb') or job.lb
        job.bm = row.get('bm') if row.get('bm') is not None else job.bm
        job.title_status = row.get('title_status') or job.title_status
        job.display_title = row.get('display_title') or job.display_title
        job.job_status = row.get('job_status') or job.job_status
        job.record_status = row.get('record_status') or job.record_status
        job.score_observation_status = so.get('status') or job.score_observation_status
        job.score_observation_value = so.get('value') if so.get('value') is not None else job.score_observation_value
        job.competition_metric_type = co.get('metric_type') or job.competition_metric_type
        job.competition_base = co.get('base') if co.get('base') is not None else job.competition_base
        job.competition_source = co.get('source') or job.competition_source
        job.ratio_comparable = row.get('ratio_comparable', job.ratio_comparable)
        if row.get('source'):
            job.source = row['source']

    async def _update_cycle_meta(self, cycle: str, meta: Dict[str, Any], row_count: int):
        """更新周期元数据"""
        result = await self.db.execute(select(Cycle).where(Cycle.cycle == cycle))
        existing = result.scalar_one_or_none()
        if existing:
            existing.total_posts = meta.get('total') or meta.get('raw_posts') or row_count
            existing.total_recruits = meta.get('recruits', 0)
            existing.score_unresolved = meta.get('score_unresolved', 0)
        else:
            self.db.add(Cycle(
                cycle=cycle,
                label=f'{cycle}年度',
                total_posts=meta.get('total') or meta.get('raw_posts') or row_count,
                total_recruits=meta.get('recruits', 0),
                score_unresolved=meta.get('score_unresolved', 0),
                status='verified',
            ))

    async def _upsert_mirror_state(self, **kwargs):
        """持久化 mirror state（P1-3：追踪 DB 镜像的是哪版 canonical）"""
        result = await self.db.execute(
            select(MirrorState).where(MirrorState.cycle == kwargs['cycle'])
        )
        existing = result.scalar_one_or_none()
        if existing:
            for k, v in kwargs.items():
                if v is not None:
                    setattr(existing, k, v)
        else:
            self.db.add(MirrorState(**kwargs))
