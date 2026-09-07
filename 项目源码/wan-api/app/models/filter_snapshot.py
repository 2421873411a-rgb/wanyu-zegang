import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class FilterSnapshot(Base):
    """用户筛选快照模型"""
    __tablename__ = "filter_snapshots"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle = Column(String(8), nullable=False)
    view = Column(String(32), nullable=False)
    filters = Column(Text, default='{}')
    metric = Column(String(32), default="jobs")
    release = Column(String(32), default="")
    created_at = Column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    
    # 关系
    user = relationship("User", back_populates="filter_snapshots")
    
    def __repr__(self):
        return f"<FilterSnapshot {self.view}>"
