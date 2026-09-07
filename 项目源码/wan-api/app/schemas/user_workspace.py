from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class SavedPositionCreate(BaseModel):
    """收藏岗位请求"""
    record_id: str
    cycle: str = Field(max_length=8)
    # v17.9.12：max_length 与列宽一致——SQLite 静默放行超长串、生产 PG 会 500（方言漂移）
    note: Optional[str] = Field(default="", max_length=500)


class SavedPositionResponse(BaseModel):
    """收藏岗位响应"""
    id: str
    record_id: str
    cycle: str
    note: str
    created_at: datetime
    
    model_config = {"from_attributes": True}


class FilterSnapshotCreate(BaseModel):
    """筛选快照请求"""
    cycle: str = Field(max_length=8)
    view: str = Field(max_length=32)
    filters: Dict[str, Any] = {}
    metric: str = Field(default="jobs", max_length=32)
    release: str = Field(default="", max_length=64)


class FilterSnapshotResponse(BaseModel):
    """筛选快照响应"""
    id: str
    cycle: str
    view: str
    filters: Dict[str, Any]
    metric: str
    release: str
    created_at: datetime
    
    model_config = {"from_attributes": True}


class CompareListCreate(BaseModel):
    """对比列表请求

    v17.9.12：删除 position 字段——服务端始终分配最小空闲槽（并发四槽模型），
    客户端传 position 曾被静默忽略，属契约误导。
    """
    record_id: str
    cycle: str = Field(max_length=8)


class CompareListResponse(BaseModel):
    """对比列表响应"""
    id: str
    record_id: str
    cycle: str
    position: int
    created_at: datetime
    
    model_config = {"from_attributes": True}
