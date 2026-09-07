from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from decimal import Decimal


class JobResponse(BaseModel):
    """岗位响应"""
    job_id: str
    cycle: str
    code: Optional[str] = None
    city: Optional[str] = None
    exam: Optional[str] = None
    unit: Optional[str] = None
    zw: Optional[str] = None
    zy: Optional[str] = None
    num: Optional[int] = None
    xl: Optional[str] = None
    xw: Optional[str] = None
    age: Optional[str] = None
    bz: Optional[str] = None
    lb: Optional[str] = None
    display_title: Optional[str] = None
    
    # 成绩观测
    score_observation_status: Optional[str] = None
    score_observation_value: Optional[Decimal] = None
    
    # 竞争观测
    competition_metric_type: Optional[str] = None
    competition_base: Optional[int] = None
    
    model_config = {"from_attributes": True}


class JobSearchRequest(BaseModel):
    """岗位搜索请求"""
    cycle: Optional[str] = None
    keyword: Optional[str] = None
    city: Optional[str] = None
    exam: Optional[str] = None
    major: Optional[str] = None
    category: Optional[str] = None
    page: int = 1
    page_size: int = 60
    sort: str = "source"


class JobSearchResponse(BaseModel):
    """岗位搜索响应"""
    total: int
    page: int
    page_size: int
    pages: int
    items: List[JobResponse]
    facets: Optional[Dict[str, Any]] = None


class JobStatsResponse(BaseModel):
    """岗位统计响应"""
    cycle: str
    total_posts: int
    total_recruits: int
    by_city: Dict[str, int]
    by_exam: Dict[str, int]
    by_category: Dict[str, int]
