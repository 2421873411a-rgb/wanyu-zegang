from datetime import datetime
from sqlalchemy import JSON, Column, String, Integer, Text, DateTime, Numeric, Boolean
from app.database import Base


class Job(Base):
    """岗位模型"""
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(128), unique=True, nullable=False, index=True)
    cycle = Column(String(8), nullable=False, index=True)
    code = Column(String(32), index=True)
    city = Column(String(32), index=True)
    exam = Column(String(64), index=True)
    unit = Column(String(256))
    zw = Column(String(256))  # 职位名称
    zy = Column(Text)  # 专业要求
    num = Column(Integer)  # 招录人数
    xl = Column(String(64))  # 学历
    xw = Column(String(64))  # 学位
    xz = Column(String(64))  # 政治面貌
    age = Column(String(128))  # 年龄要求
    bz = Column(Text)  # 备注
    lb = Column(String(64), index=True)  # 岗位类型
    title_status = Column(String(32))
    display_title = Column(String(256))
    job_status = Column(String(32), default="active")
    
    # 成绩观测
    score_observation_status = Column(String(32))
    score_observation_scale_id = Column(String(32))
    score_observation_value = Column(Numeric)
    
    # 竞争观测
    competition_metric_type = Column(String(32))
    competition_base = Column(Integer)
    competition_source = Column(String(128))
    ratio_comparable = Column(Boolean, default=False)
    
    # 证据来源（SQLite用Text存储JSON）
    source = Column(JSON, default=dict)
    
    created_at = Column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<Job {self.job_id}>"
