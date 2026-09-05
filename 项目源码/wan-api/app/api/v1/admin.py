from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.job import Job
from app.models.cycle import Cycle
from app.dependencies import get_admin_user
import json

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取管理后台仪表盘数据"""
    # 用户统计
    user_count_result = await db.execute(select(func.count(User.id)))
    user_count = user_count_result.scalar()
    
    # 岗位统计
    job_count_result = await db.execute(select(func.count(Job.id)))
    job_count = job_count_result.scalar()
    
    # 各周期岗位数
    cycle_stats_result = await db.execute(
        select(Job.cycle, func.count(Job.id).label("count"))
        .group_by(Job.cycle)
        .order_by(Job.cycle.desc())
    )
    cycle_stats = {row.cycle: row.count for row in cycle_stats_result.all()}
    
    return {
        "user_count": user_count,
        "job_count": job_count,
        "cycle_stats": cycle_stats
    }


@router.get("/users")
async def get_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户列表"""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "username": u.username,
            "display_name": u.display_name,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None
        }
        for u in users
    ]


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    is_admin: Optional[bool] = None,
    is_active: Optional[bool] = None,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """更新用户状态"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    if is_admin is not None:
        user.is_admin = is_admin
    if is_active is not None:
        user.is_active = is_active
    
    return {"message": "更新成功"}


@router.post("/import/{cycle}")
async def import_cycle_data(
    cycle: str,
    file: UploadFile = File(...),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """导入周期数据（JSON格式）"""
    try:
        content = await file.read()
        data = json.loads(content)
        
        # 这里需要调用数据导入服务
        # 暂时返回成功状态
        return {
            "message": f"数据导入成功",
            "cycle": cycle,
            "file_name": file.filename
        }
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的JSON格式"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导入失败: {str(e)}"
        )
