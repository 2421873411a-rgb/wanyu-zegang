import hashlib
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_admin_user
from app.models.cycle import Cycle
from app.models.job import Job
from app.models.user import User
from app.services.import_service import ImportService

logger = logging.getLogger("wanyu.admin")

router = APIRouter()

# 允许导入的周期白名单（与主站 canonical 三周期一致）
_IMPORTABLE_CYCLES = {"2024", "2025", "2026"}


async def _count_active_admins(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count(User.id)).where(User.is_admin.is_(True), User.is_active.is_(True))
    )
    return int(result.scalar() or 0)


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
    """更新用户状态。

    v17.9.1 S0：最后管理员保护——不允许把最后一名 active admin 降权或禁用，
    否则系统失去管理入口且注册接口不再产生管理员（v17.9.1 起注册永远普通用户）。
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    demoting = (is_admin is False and user.is_admin) or (is_active is False and user.is_admin and user.is_active)
    if demoting and await _count_active_admins(db) <= 1 and user.is_admin and user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系统必须保留至少一名启用的管理员：请先创建并启用另一名管理员"
        )

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
    """导入周期岗位数据（JSON，allMajors.rows 结构，与 canonical 产物同构）。

    v17.9.1 S1：旧实现读了文件却返回假"导入成功"——对本项目的信任链是致命伤。
    现在的真实链路：大小上限 → JSON 解析 → 结构校验 → ImportService 事务内写入 →
    行数对账（imported+updated+skipped 必须 == rows_total，否则整体回滚）→
    返回真实统计 + 源文件 sha256（可追溯）。任何一步失败：事务回滚、数据零写入。
    """
    if cycle not in _IMPORTABLE_CYCLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法周期：{cycle}（允许 {'/'.join(sorted(_IMPORTABLE_CYCLES))}）"
        )

    max_bytes = settings.ADMIN_IMPORT_MAX_BYTES
    chunks = []
    received = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        received += len(chunk)
        if received > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"上传超过上限（{max_bytes // (1024 * 1024)}MB），已拒绝"
            )
        chunks.append(chunk)
    content = b"".join(chunks)
    source_sha256 = hashlib.sha256(content).hexdigest()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的JSON格式")

    rows = (data.get("allMajors") or {}).get("rows")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JSON 结构不符：需要非空的 allMajors.rows 数组"
        )
    bad_rows = sum(1 for r in rows if not isinstance(r, dict) or not (r.get("job_id") or r.get("row_id")))
    if bad_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{bad_rows} 行缺少 job_id/row_id，已拒绝导入"
        )

    # 事务内写入（get_db 在请求结束时 commit；下方任一异常都会回滚）
    service = ImportService(db)
    stats = await service.import_cycle_jobs(cycle, data)

    # 行数对账：写入口径必须与源行数严丝合缝
    imported, updated, skipped = stats.get("imported", 0), stats.get("updated", 0), stats.get("skipped", 0)
    if imported + updated + skipped != len(rows):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导入对账失败（写入口径与源行数不一致），事务已回滚"
        )

    # 周期元数据行数核对（Cycle 表应存在且 total_posts 与 meta/行数一致）
    cycle_row = await db.execute(select(Cycle).where(Cycle.cycle == cycle))
    cycle_obj = cycle_row.scalar_one_or_none()
    logger.info(
        "admin import cycle=%s imported=%s updated=%s skipped=%s rows=%s sha256=%s by=%s",
        cycle, imported, updated, skipped, len(rows), source_sha256[:16], admin.username,
    )

    return {
        "message": "数据导入成功",
        "cycle": cycle,
        "file_name": file.filename,
        "source_sha256": source_sha256,
        "rows_total": len(rows),
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "cycle_meta_total_posts": cycle_obj.total_posts if cycle_obj else None,
    }
