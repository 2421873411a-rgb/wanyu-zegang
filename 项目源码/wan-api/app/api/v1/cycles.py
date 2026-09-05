from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.cycle import Cycle

router = APIRouter()


@router.get("")
async def get_cycles(db: AsyncSession = Depends(get_db)):
    """获取所有周期列表"""
    result = await db.execute(select(Cycle).order_by(Cycle.cycle.desc()))
    cycles = result.scalars().all()
    
    return [
        {
            "cycle": c.cycle,
            "label": c.label,
            "total_posts": c.total_posts,
            "total_recruits": c.total_recruits,
            "status": c.status,
            "snapshot_date": c.snapshot_date
        }
        for c in cycles
    ]


@router.get("/{cycle}")
async def get_cycle(cycle: str, db: AsyncSession = Depends(get_db)):
    """获取单个周期详情"""
    result = await db.execute(select(Cycle).where(Cycle.cycle == cycle))
    c = result.scalar_one_or_none()
    
    if not c:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="周期不存在")
    
    return {
        "cycle": c.cycle,
        "label": c.label,
        "total_posts": c.total_posts,
        "total_recruits": c.total_recruits,
        "score_unresolved": c.score_unresolved,
        "evidence_level": c.evidence_level,
        "status": c.status,
        "snapshot_date": c.snapshot_date,
        "gaps": c.gaps
    }
