import math
import re
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from app.database import get_db
from app.models.job import Job
from app.schemas.job import JobResponse, JobSearchResponse

router = APIRouter()

# v17.9.12：用户输入里的 % _ \ 是 LIKE 通配符/转义符，必须转义后才能参与模糊匹配
# （keyword='%%' 曾语义变成"匹配全部"）；控制字符（含 NUL）在 asyncpg 下会直接 500。
# 转义集必须含反斜杠自身（用户输入的反斜杠会充当 ESCAPE 字符重臂通配符，
# 生产 PG 还会报 invalid escape）——v17.9.13 曾声称修了但代码未落地，回归审计抓出。
_LIKE_ESC = re.compile(r"([\\%_])")


def _escape_like(value: str) -> str:
    # chr(92)=backslash; lambda builds replacement so no template escaping can corrupt it (v17.9.12 once shipped backslash+SOH here)
    return _LIKE_ESC.sub(lambda m: chr(92) + m.group(1), value)


def _reject_control_chars(*values: Optional[str]) -> None:
    for v in values:
        if v and any(ord(c) < 0x20 for c in v):
            raise HTTPException(status_code=422, detail="输入包含非法控制字符")


# v17.9.12：统计结果进程内 TTL 缓存（数据只在导入后变化，每次全表聚合 ~90ms 纯浪费；
# 跨进程失效由 TTL 兜底，单 worker 部署下导入即重启，天然一致）
_STATS_CACHE: dict = {}
_STATS_TTL_SECONDS = 60.0
_STATS_CACHE_MAX = 64  # cycle 参数无校验曾使键空间无界（3000 匿名请求实测不释放）


def _cached(key: str, builder):
    hit = _STATS_CACHE.get(key)
    now = time.monotonic()
    if hit and now - hit[0] < _STATS_TTL_SECONDS:
        return hit[1]
    value = builder()
    _STATS_CACHE[key] = (now, value)
    return value


async def _cached_async(key: str, abuilder):
    hit = _STATS_CACHE.get(key)
    now = time.monotonic()
    if hit and now - hit[0] < _STATS_TTL_SECONDS:
        return hit[1]
    value = await abuilder()
    if len(_STATS_CACHE) >= _STATS_CACHE_MAX:
        _STATS_CACHE.clear()  # 容量上限：宁可整体失效也不无界增长
    _STATS_CACHE[key] = (now, value)
    return value


def invalidate_stats_cache() -> None:
    """数据导入后必须调用：否则 admin 热导入后 stats 有 60s 脏读窗口。"""
    _STATS_CACHE.clear()


@router.get("/search", response_model=JobSearchResponse)
async def search_jobs(
    cycle: Optional[str] = Query(None, max_length=8, description="周期（2024/2025/2026）"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    city: Optional[str] = Query(None, description="城市"),
    exam: Optional[str] = Query(None, description="考试类别"),
    major: Optional[str] = Query(None, description="专业"),
    category: Optional[str] = Query(None, description="岗位类别"),
    page: int = Query(1, ge=1, le=10000, description="页码（上限防御深翻页与溢出）"),
    page_size: int = Query(60, ge=1, le=200, description="每页数量"),
    sort: str = Query("source", description="排序方式"),
    db: AsyncSession = Depends(get_db)
):
    """搜索岗位（只返回 record_status='active' 的岗位；excluded 是快照下线行，
    仅审计/管理入口可见）"""
    _reject_control_chars(keyword, major, city, exam, category)
    query = select(Job)
    count_query = select(func.count(Job.id))

    # 应用筛选条件
    filters = [Job.record_status == "active"]
    if cycle:
        filters.append(Job.cycle == cycle)
    if city:
        filters.append(Job.city == city)
    if exam:
        filters.append(Job.exam == exam)
    if category:
        filters.append(Job.lb == category)
    if major:
        # 专业模糊搜索（通配符已转义）
        filters.append(Job.zy.ilike(f"%{_escape_like(major)}%", escape="\\"))
    if keyword:
        # 关键词搜索（职位名称、单位、专业；通配符已转义）
        kw = _escape_like(keyword)
        keyword_filter = or_(
            Job.unit.ilike(f"%{kw}%", escape="\\"),
            Job.zw.ilike(f"%{kw}%", escape="\\"),
            Job.zy.ilike(f"%{kw}%", escape="\\"),
            Job.code.ilike(f"%{kw}%", escape="\\")
        )
        filters.append(keyword_filter)
    
    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # 应用排序
    if sort == "recruits":
        query = query.order_by(Job.num.desc().nullslast())
    elif sort == "code":
        query = query.order_by(Job.code)
    else:
        query = query.order_by(Job.id)
    
    # 分页
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    # 执行查询
    result = await db.execute(query)
    jobs = result.scalars().all()
    
    # 计算总页数
    pages = math.ceil(total / page_size) if total > 0 else 1
    
    return JobSearchResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        items=[JobResponse.model_validate(job) for job in jobs]
    )


@router.get("/{record_id}", response_model=JobResponse)
async def get_job(
    record_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取岗位详情（excluded 下线行按不存在处理，404）"""
    result = await db.execute(
        select(Job).where(Job.job_id == record_id, Job.record_status == "active")
    )
    job = result.scalar_one_or_none()
    
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="岗位不存在")
    
    return JobResponse.model_validate(job)


@router.get("/stats/by-city")
async def get_jobs_by_city(
    cycle: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """按城市统计岗位数量（仅 active）"""
    query = select(Job.city, func.count(Job.id).label("count"))
    query = query.where(Job.record_status == "active")
    if cycle:
        query = query.where(Job.cycle == cycle)
    query = query.group_by(Job.city).order_by(func.count(Job.id).desc())

    async def _build() -> dict:
        result = await db.execute(query)
        rows = result.all()
        return {row.city: row.count for row in rows if row.city}

    return await _cached_async(f"city:{cycle or '*'}", _build)


@router.get("/stats/by-exam")
async def get_jobs_by_exam(
    cycle: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """按考试类别统计岗位数量（仅 active）"""
    query = select(Job.exam, func.count(Job.id).label("count"))
    query = query.where(Job.record_status == "active")
    if cycle:
        query = query.where(Job.cycle == cycle)
    query = query.group_by(Job.exam).order_by(func.count(Job.id).desc())

    async def _build() -> dict:
        result = await db.execute(query)
        rows = result.all()
        return {row.exam: row.count for row in rows if row.exam}

    return await _cached_async(f"exam:{cycle or '*'}", _build)
