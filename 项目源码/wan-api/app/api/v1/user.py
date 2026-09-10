import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.database import get_db
from app.models.user import User
from app.models.saved_position import SavedPosition
from app.models.filter_snapshot import FilterSnapshot
from app.models.compare_list import CompareList
from app.schemas.user_workspace import (
    SavedPositionCreate, SavedPositionResponse,
    FilterSnapshotCreate, FilterSnapshotResponse,
    CompareListCreate, CompareListResponse
)
from app.dependencies import get_current_user
from app.models.job import Job

router = APIRouter()


async def _require_active_job(db: AsyncSession, record_id: str, cycle: str) -> None:
    """收藏/对比的引用目标必须是当前 active 且周期一致的岗位（v17.9.11 P1）。

    原先接受任意字符串：excluded 岗位成为"列表可见、详情 404"的幽灵引用，
    伪造 id 还会永久占用对比槽位。add 时即拒绝，引用与公共可见面永远一致。
    """
    result = await db.execute(
        select(Job).where(
            Job.job_id == record_id,
            Job.cycle == cycle,
            Job.record_status == "active",
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="岗位不存在或已下线（record_id 必须指向当前 active 岗位且周期一致）"
        )


# ============ 收藏岗位 ============

@router.get("/positions", response_model=List[SavedPositionResponse])
async def get_saved_positions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取我的收藏列表"""
    result = await db.execute(
        select(SavedPosition)
        .where(SavedPosition.user_id == current_user.id)
        .order_by(SavedPosition.created_at.desc())
    )
    positions = result.scalars().all()
    return [SavedPositionResponse.model_validate(p) for p in positions]


@router.post("/positions", response_model=SavedPositionResponse, status_code=status.HTTP_201_CREATED)
async def add_saved_position(
    data: SavedPositionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """收藏岗位"""
    await _require_active_job(db, data.record_id, data.cycle)
    # 检查是否已收藏
    result = await db.execute(
        select(SavedPosition).where(
            SavedPosition.user_id == current_user.id,
            SavedPosition.record_id == data.record_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该岗位已收藏"
        )
    
    position = SavedPosition(
        user_id=current_user.id,
        record_id=data.record_id,
        cycle=data.cycle,
        note=data.note
    )
    db.add(position)
    try:
        await db.flush()
    except IntegrityError:
        # v17.9.1 S1：并发下 check-then-insert 的竞态由数据库 UNIQUE(user_id, record_id) 兜底
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该岗位已收藏"
        )

    return SavedPositionResponse.model_validate(position)


@router.delete("/positions/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_saved_position(
    record_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """取消收藏"""
    result = await db.execute(
        select(SavedPosition).where(
            SavedPosition.user_id == current_user.id,
            SavedPosition.record_id == record_id
        )
    )
    position = result.scalar_one_or_none()
    
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="收藏记录不存在"
        )
    
    await db.delete(position)


# ============ 筛选快照 ============

@router.get("/snapshots", response_model=List[FilterSnapshotResponse])
async def get_snapshots(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取我的筛选快照（filters 列为 Text 存 JSON 字符串，读出时反序列化）"""
    result = await db.execute(
        select(FilterSnapshot)
        .where(FilterSnapshot.user_id == current_user.id)
        .order_by(FilterSnapshot.created_at.desc())
    )
    snapshots = result.scalars().all()
    items = []
    for s in snapshots:
        items.append(_snapshot_response(s))
    return items


def _snapshot_response(s) -> "FilterSnapshotResponse":
    """filters 列是 Text 存 JSON 字符串——先反序列化再构造响应模型
    （model_validate 会直接校验 ORM 属性，str→Dict 在构造期就炸，这正是 P0 读路径）。"""
    return FilterSnapshotResponse(
        id=s.id, cycle=s.cycle, view=s.view,
        filters=json.loads(s.filters or "{}"),
        metric=s.metric, release=s.release, created_at=s.created_at,
    )


@router.post("/snapshots", response_model=FilterSnapshotResponse, status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    data: FilterSnapshotCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """保存筛选快照（v17.9.12 P0：filters 序列化为 JSON 字符串落 Text 列。

    原实现把 dict 直接绑到 Text 列 → 写路径 100% 500；读路径 str→Dict 校验
    二次 500；前端静默吞错造成"已保存"假象。另加防滥用上限：单份 ≤32KB、
    每用户 ≤50 份。
    """
    filters_json = json.dumps(data.filters, ensure_ascii=False)
    if len(filters_json.encode("utf-8")) > 32 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="筛选快照过大（>32KB）")
    # v17.10.2 P2-08：配额从应用约定升级为事务约定。count→insert 的并发窗口
    # 在 49+并发 时可突破 50；PostgreSQL 用事务级咨询锁把同用户的配额检查串行化
    # （锁随 get_db 的事务提交/回滚自动释放）。SQLite 单写者天然串行，无需加锁。
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:uid))"),
            {"uid": str(current_user.id)},
        )
    count_result = await db.execute(
        select(func.count(FilterSnapshot.id)).where(FilterSnapshot.user_id == current_user.id)
    )
    if int(count_result.scalar() or 0) >= 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="筛选快照数量已达上限（50）")
    snapshot = FilterSnapshot(
        user_id=current_user.id,
        cycle=data.cycle,
        view=data.view,
        filters=filters_json,
        metric=data.metric,
        release=data.release
    )
    db.add(snapshot)
    await db.flush()

    return _snapshot_response(snapshot)


@router.delete("/snapshots/{snapshot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_snapshot(
    snapshot_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除筛选快照"""
    result = await db.execute(
        select(FilterSnapshot).where(
            FilterSnapshot.id == snapshot_id,
            FilterSnapshot.user_id == current_user.id
        )
    )
    snapshot = result.scalar_one_or_none()
    
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="快照不存在"
        )
    
    await db.delete(snapshot)


# ============ 对比列表 ============

@router.get("/compare", response_model=List[CompareListResponse])
async def get_compare_list(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取我的对比列表"""
    result = await db.execute(
        select(CompareList)
        .where(CompareList.user_id == current_user.id)
        .order_by(CompareList.position)
    )
    items = result.scalars().all()
    return [CompareListResponse.model_validate(item) for item in items]


@router.post("/compare", response_model=CompareListResponse, status_code=status.HTTP_201_CREATED)
async def add_to_compare(
    data: CompareListCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """添加到对比列表"""
    await _require_active_job(db, data.record_id, data.cycle)
    # 检查是否已在列表中
    result = await db.execute(
        select(CompareList).where(
            CompareList.user_id == current_user.id,
            CompareList.record_id == data.record_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该岗位已在对比列表中"
        )
    
    # P1-8：四槽模型——数据库 CHECK(0..3) + UNIQUE(user_id,position) 保证并发 ≤4
    # v17.10.2 P2-09：并发挑中同一空闲槽位会撞 UNIQUE(user_id,position)。此前一律
    # 报「该岗位已在对比列表中」——语义错误。现在：撞槽 → 回滚 → 重读槽位 → 重试，
    # 重试前先分辨「重复岗位」（record 已存在）与「槽位已满」（4/4），最多重试 3 次。
    for attempt in range(4):
        occupied_result = await db.execute(
            select(CompareList.position).where(CompareList.user_id == current_user.id)
        )
        occupied = {row for row in occupied_result.scalars().all()}
        free_slots = [s for s in range(4) if s not in occupied]
        if not free_slots:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="对比列表最多4个岗位"
            )

        item = CompareList(
            user_id=current_user.id,
            record_id=data.record_id,
            cycle=data.cycle,
            position=free_slots[0]
        )
        db.add(item)
        try:
            await db.flush()
            break
        except IntegrityError:
            await db.rollback()
            duplicate = (await db.execute(
                select(CompareList.id).where(
                    CompareList.user_id == current_user.id,
                    CompareList.record_id == data.record_id,
                )
            )).scalar_one_or_none()
            if duplicate is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="该岗位已在对比列表中"
                )
            if attempt == 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="对比操作并发冲突，请重试"
                )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="对比列表写入异常，请重试"
        )

    return CompareListResponse.model_validate(item)


@router.delete("/compare/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_compare(
    record_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """从对比列表移除"""
    result = await db.execute(
        select(CompareList).where(
            CompareList.user_id == current_user.id,
            CompareList.record_id == record_id
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="对比记录不存在"
        )
    
    await db.delete(item)
