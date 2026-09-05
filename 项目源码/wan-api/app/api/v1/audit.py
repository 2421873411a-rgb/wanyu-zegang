from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.review_event import ReviewEvent

router = APIRouter()


@router.get("/review-queue")
async def get_review_queue(
    kind: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """获取复核队列"""
    query = select(ReviewEvent)
    
    if kind:
        query = query.where(ReviewEvent.kind == kind)
    if severity:
        query = query.where(ReviewEvent.severity == severity)
    if status:
        query = query.where(ReviewEvent.status == status)
    
    query = query.order_by(ReviewEvent.created_at.desc())
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    return [
        {
            "id": e.id,
            "kind": e.kind,
            "severity": e.severity,
            "cycle": e.cycle,
            "title": e.title,
            "detail": e.detail,
            "evidence": e.evidence,
            "occurrences": e.occurrences,
            "status": e.status,
            "created_at": e.created_at.isoformat() if e.created_at else None
        }
        for e in events
    ]
