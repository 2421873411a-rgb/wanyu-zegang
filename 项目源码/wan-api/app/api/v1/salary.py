from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.salary_data import SalaryData

router = APIRouter()


@router.get("")
async def get_salary(
    city: Optional[str] = None,
    employment_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取待遇数据"""
    query = select(SalaryData)
    
    if city:
        query = query.where(SalaryData.city == city)
    if employment_type:
        query = query.where(SalaryData.employment_type == employment_type)
    
    result = await db.execute(query)
    salaries = result.scalars().all()
    
    # 按城市和类型组织数据
    data = {}
    for s in salaries:
        if s.city not in data:
            data[s.city] = {}
        if s.employment_type not in data[s.city]:
            data[s.city][s.employment_type] = {}
        data[s.city][s.employment_type][s.stage] = float(s.value_wan) if s.value_wan else None
    
    return data


@router.get("/ranking")
async def get_salary_ranking(
    employment_type: str = "公务员",
    stage: str = "3年",
    db: AsyncSession = Depends(get_db)
):
    """获取城市待遇排行"""
    result = await db.execute(
        select(SalaryData)
        .where(
            SalaryData.employment_type == employment_type,
            SalaryData.stage == stage
        )
        .order_by(SalaryData.value_wan.desc().nullslast())
    )
    salaries = result.scalars().all()
    
    return [
        {
            "city": s.city,
            "value_wan": float(s.value_wan) if s.value_wan else None
        }
        for s in salaries
    ]
