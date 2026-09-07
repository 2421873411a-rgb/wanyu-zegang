from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
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

router = APIRouter()


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
    """获取我的筛选快照"""
    result = await db.execute(
        select(FilterSnapshot)
        .where(FilterSnapshot.user_id == current_user.id)
        .order_by(FilterSnapshot.created_at.desc())
    )
    snapshots = result.scalars().all()
    return [FilterSnapshotResponse.model_validate(s) for s in snapshots]


@router.post("/snapshots", response_model=FilterSnapshotResponse, status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    data: FilterSnapshotCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """保存筛选快照"""
    snapshot = FilterSnapshot(
        user_id=current_user.id,
        cycle=data.cycle,
        view=data.view,
        filters=data.filters,
        metric=data.metric,
        release=data.release
    )
    db.add(snapshot)
    await db.flush()
    
    return FilterSnapshotResponse.model_validate(snapshot)


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
    # 不再靠应用层 count（并发窗口可突破），改找最小空闲槽位
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
    except IntegrityError:
        # v17.9.1 S1：并发竞态由 UNIQUE(user_id, record_id) 兜底；上限 4 由应用层在
        # 同一事务内 count 校验（固定槽位设计可彻底消除竞态，见 S6 契约文档备注）
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该岗位已在对比列表中"
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
