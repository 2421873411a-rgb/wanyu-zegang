import hashlib
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_admin_user
from app.models.job import Job
from app.models.mirror_state import MirrorState
from app.models.user import User
from app.services.import_service import ImportService, SnapshotValidationError

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

    # 岗位统计（v17.9.11：active 与 excluded 分列，job_count 与 Cycle 表口径一致，
    # 不再把下线行混进总数误导对账）
    job_count_result = await db.execute(
        select(func.count(Job.id)).where(Job.record_status == "active")
    )
    job_count = job_count_result.scalar()
    excluded_result = await db.execute(
        select(func.count(Job.id)).where(Job.record_status == "excluded")
    )
    excluded_count = excluded_result.scalar()

    # 各周期岗位数（active 口径）
    cycle_stats_result = await db.execute(
        select(Job.cycle, func.count(Job.id).label("count"))
        .where(Job.record_status == "active")
        .group_by(Job.cycle)
        .order_by(Job.cycle.desc())
    )
    cycle_stats = {row.cycle: row.count for row in cycle_stats_result.all()}

    return {
        "user_count": user_count,
        "job_count": job_count,
        "excluded_count": excluded_count,
        "cycle_stats": cycle_stats
    }


@router.get("/users")
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户列表（分页；v17.9.18 规模防御）"""
    total_result = await db.execute(select(func.count(User.id)))
    total = int(total_result.scalar() or 0)
    result = await db.execute(
        select(User)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
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
    }


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
    if demoting and user.is_admin and user.is_active:
        # 最后管理员保护（v17.9.12 并发加固）：
        # 1) PG advisory 事务锁串行化"检查+写入"——否则两名管理员并发互降时
        #    两个守卫可同读旧状态全部放行，清零管理入口；
        # 2) 计数排除"本次降权目标"：串行化后第二笔守卫看到第一笔已提交的结果，
        #    目标之外无其他 admin → 拒绝。
        # SQLite（测试环境）为单写者，advisory lock 不存在则跳过，残余窗口仅理论存在。
        try:
            await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('wanyu-last-admin-guard'))"))
        except Exception:
            pass
        others = await db.execute(
            select(func.count(User.id)).where(
                User.is_admin.is_(True),
                User.is_active.is_(True),
                User.id != user.id,
            )
        )
        if int(others.scalar() or 0) < 1:
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
    """导入周期岗位数据（快照替换，fail-closed 强校验后才允许写库）。

    v17.9.10：
    - 校验全部在写库前完成（meta 必填守恒 / job_id 强格式 ^job-<cycle>-<20hex> /
      重复 / 排除行证据 / provenance 指纹）；任一违规 → 400、零写入
    - 同时接受 canonical 键 all_majors 与静态派生键 allMajors
    - 快照替换：exact overwrite（源清空 → DB 清空）、重新出现自动恢复 active、
      DB 有但快照没有 → record_status='excluded'
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
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"上传超过上限（{max_bytes // (1024 * 1024)}MB），已拒绝"
            )
        chunks.append(chunk)
    content = b"".join(chunks)
    source_sha256 = hashlib.sha256(content).hexdigest()

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, RecursionError, UnicodeDecodeError, ValueError):
        # RecursionError：超深嵌套 JSON；ValueError 兜底其余解析异常——统一 400 而非 500
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的JSON格式")
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JSON 顶层必须是对象")

    # 快照替换（事务内：校验→写入→stale 下线→mirror state）；校验失败 → 400 零写入
    service = ImportService(db)
    try:
        stats = await service.snapshot_replace(cycle, data, source_sha256=source_sha256)
    except SnapshotValidationError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"快照校验失败（已拒绝导入，数据库零写入）：{exc}"
        )

    from app.api.v1.jobs import invalidate_stats_cache
    invalidate_stats_cache()

    imported = stats.get("imported", 0)
    updated = stats.get("updated", 0)
    deactivated = stats.get("deactivated", 0)
    rows_total = stats.get("incoming_rows", 0)
    if imported + updated != rows_total:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="导入对账失败（写入口径与源行数不一致），事务已回滚"
        )

    # v17.9.11：返回全周期镜像摘要——管理员单周期导入造成的跨周期版本错位
    # 必须当场可见，而不是事后去查 mirror_state 表。
    mirror_rows = (await db.execute(select(MirrorState).order_by(MirrorState.cycle))).scalars().all()
    mirror_summary = {
        m.cycle: {
            "release": m.release,
            "source_sha256": (m.source_sha256 or "")[:16],
            "job_id_set_sha256": (m.job_id_set_sha256 or "")[:16],
        }
        for m in mirror_rows
    }

    logger.info(
        "admin import cycle=%s imported=%s updated=%s deactivated=%s rows=%s sha256=%s by=%s",
        cycle, imported, updated, deactivated, rows_total,
        source_sha256[:16], admin.username,
    )

    return {
        "message": "数据导入成功（快照替换）",
        "cycle": cycle,
        "file_name": file.filename,
        "source_sha256": source_sha256,
        "rows_total": rows_total,
        "imported": imported,
        "updated": updated,
        "deactivated": deactivated,
        "active_rows": stats.get("active_rows"),
        "job_id_set_sha256": stats.get("job_id_set_sha256", ""),
        "mirror_states": mirror_summary,
    }
