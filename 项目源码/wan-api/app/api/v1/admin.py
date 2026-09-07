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
    """导入周期岗位数据（快照替换，强校验后才允许写库）。

    v17.9.9 P1-1/P1-2/P1-3：
    - 校验全部在写库前完成（job_id 格式/周期一致性/重复/meta 守恒）
    - 截断但合法的非空文件会被 meta 守恒拦住
    - job_id 周期不匹配会被拒绝（防止 job-2024-* 混入 2026）
    - 快照替换：DB 中该周期已有但快照中没有的行 → record_status='excluded'
    - mirror_state 持久化：追踪 DB 镜像的是哪版 canonical
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

    # P1-1：强校验（全部在写库前完成）
    from app.services.import_service import validate_snapshot
    violations = validate_snapshot(cycle, data)
    if violations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"快照校验失败（{len(violations)} 项违规）：{'；'.join(violations[:5])}"
        )

    # 快照替换导入（事务内：新行+全量更新+缺失行 deactivate+mirror state）
    service = ImportService(db)
    release = (data.get('allMajors') or {}).get('meta', {}).get('release', '')
    stats = await service.snapshot_replace(
        cycle=cycle,
        data=data,
        source_sha256=source_sha256,
        release=release,
    )

    imported = stats.get('imported', 0)
    updated = stats.get('updated', 0)
    deactivated = stats.get('deactivated', 0)

    logger.info(
        "admin import cycle=%s imported=%s updated=%s deactivated=%s rows=%s sha256=%s by=%s",
        cycle, imported, updated, deactivated, stats.get('incoming_rows', 0),
        source_sha256[:16], admin.username,
    )

    return {
        "message": "数据导入成功（快照替换）",
        "cycle": cycle,
        "file_name": file.filename,
        "source_sha256": source_sha256,
        "rows_total": stats.get('incoming_rows', 0),
        "imported": imported,
        "updated": updated,
        "deactivated": deactivated,
        "job_id_set_sha256": stats.get('job_id_set_sha256', ''),
    }
