import hashlib
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
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
_IMPORTABLE_CYCLES = {"2024", "2025", "2026"}


async def _count_active_admins(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count(User.id)).where(User.is_admin.is_(True), User.is_active.is_(True))
    )
    return int(result.scalar() or 0)


@router.get("/dashboard")
async def get_dashboard(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user_count = (await db.execute(select(func.count(User.id)))).scalar()
    job_count = (await db.execute(select(func.count(Job.id)))).scalar()
    cycle_stats_result = await db.execute(
        select(Job.cycle, func.count(Job.id).label("count"))
        .group_by(Job.cycle)
        .order_by(Job.cycle.desc())
    )
    return {
        "user_count": user_count,
        "job_count": job_count,
        "cycle_stats": {row.cycle: row.count for row in cycle_stats_result.all()},
    }


@router.get("/users")
async def get_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    users = (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "username": u.username,
            "display_name": u.display_name,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        }
        for u in users
    ]


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    is_admin: Optional[bool] = None,
    is_active: Optional[bool] = None,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    demoting = (is_admin is False and user.is_admin) or (
        is_active is False and user.is_admin and user.is_active
    )
    if demoting and await _count_active_admins(db) <= 1 and user.is_admin and user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系统必须保留至少一名启用的管理员：请先创建并启用另一名管理员",
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
    db: AsyncSession = Depends(get_db),
):
    """导入完整周期快照。

    同时接受静态派生产物 `allMajors` 与正式 canonical `all_majors` 结构；写入
    是镜像同步而非累积 upsert：全字段覆盖，并删除该周期源快照已不存在的岗位。
    """
    if cycle not in _IMPORTABLE_CYCLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法周期：{cycle}（允许 {'/'.join(sorted(_IMPORTABLE_CYCLES))}）",
        )

    max_bytes = settings.ADMIN_IMPORT_MAX_BYTES
    chunks: list[bytes] = []
    received = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        received += len(chunk)
        if received > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"上传超过上限（{max_bytes // (1024 * 1024)}MB），已拒绝",
            )
        chunks.append(chunk)

    content = b"".join(chunks)
    source_sha256 = hashlib.sha256(content).hexdigest()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="无效的JSON格式") from exc

    group = data.get("allMajors") or data.get("all_majors") or {}
    rows = group.get("rows") if isinstance(group, dict) else None
    if not isinstance(rows, list) or not rows:
        raise HTTPException(
            status_code=400,
            detail="JSON 结构不符：需要非空的 allMajors.rows 或 all_majors.rows 数组",
        )
    bad_rows = sum(
        1 for row in rows
        if not isinstance(row, dict) or not (row.get("job_id") or row.get("row_id"))
    )
    if bad_rows:
        raise HTTPException(status_code=400, detail=f"{bad_rows} 行缺少 job_id/row_id，已拒绝导入")

    service = ImportService(db)
    stats = await service.import_cycle_jobs(cycle, data)
    imported = stats.get("imported", 0)
    updated = stats.get("updated", 0)
    skipped = stats.get("skipped", 0)
    deleted = stats.get("deleted", 0)
    if imported + updated + skipped != len(rows):
        raise HTTPException(
            status_code=500,
            detail="导入对账失败（写入口径与源行数不一致），事务已回滚",
        )

    cycle_obj = (await db.execute(select(Cycle).where(Cycle.cycle == cycle))).scalar_one_or_none()
    logger.info(
        "admin snapshot import cycle=%s imported=%s updated=%s deleted=%s skipped=%s rows=%s sha256=%s by=%s",
        cycle, imported, updated, deleted, skipped, len(rows), source_sha256[:16], admin.username,
    )
    return {
        "message": "数据镜像同步成功",
        "cycle": cycle,
        "file_name": file.filename,
        "source_sha256": source_sha256,
        "rows_total": len(rows),
        "imported": imported,
        "updated": updated,
        "deleted": deleted,
        "skipped": skipped,
        "cycle_meta_total_posts": cycle_obj.total_posts if cycle_obj else None,
    }
