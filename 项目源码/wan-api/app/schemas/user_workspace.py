from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class SavedPositionCreate(BaseModel):
    """收藏岗位请求"""
    record_id: str
    cycle: str
    note: Optional[str] = ""


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
    cycle: str
    view: str
    filters: Dict[str, Any] = {}
    metric: str = "jobs"
    release: str = ""


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
    """对比列表请求"""
    record_id: str
    cycle: str
    position: int = 0


class CompareListResponse(BaseModel):
    """对比列表响应"""
    id: str
    record_id: str
    cycle: str
    position: int
    created_at: datetime
    
    model_config = {"from_attributes": True}
