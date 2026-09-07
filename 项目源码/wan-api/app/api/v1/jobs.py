import math
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from app.database import get_db
from app.models.job import Job
from app.schemas.job import JobResponse, JobSearchResponse

router = APIRouter()


@router.get("/search", response_model=JobSearchResponse)
async def search_jobs(
    cycle: Optional[str] = Query(None, description="周期（2024/2025/2026）"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    city: Optional[str] = Query(None, description="城市"),
    exam: Optional[str] = Query(None, description="考试类别"),
    major: Optional[str] = Query(None, description="专业"),
    category: Optional[str] = Query(None, description="岗位类别"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(60, ge=1, le=200, description="每页数量"),
    sort: str = Query("source", description="排序方式"),
    db: AsyncSession = Depends(get_db)
):
    """搜索岗位（只返回 record_status='active' 的岗位；excluded 是快照下线行，
    仅审计/管理入口可见）"""
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
        # 专业模糊搜索
        filters.append(Job.zy.ilike(f"%{major}%"))
    if keyword:
        # 关键词搜索（职位名称、单位、专业）
        keyword_filter = or_(
            Job.unit.ilike(f"%{keyword}%"),
            Job.zw.ilike(f"%{keyword}%"),
            Job.zy.ilike(f"%{keyword}%"),
            Job.code.ilike(f"%{keyword}%")
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
    
    result = await db.execute(query)
    rows = result.all()
    
    return {row.city: row.count for row in rows if row.city}


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
    
    result = await db.execute(query)
    rows = result.all()
    
    return {row.exam: row.count for row in rows if row.exam}
