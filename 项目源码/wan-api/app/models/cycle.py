from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text
from app.database import Base


class Cycle(Base):
    """周期元数据模型"""
    __tablename__ = "cycles"
    
    cycle = Column(String(8), primary_key=True)
    label = Column(String(64), nullable=False)
    total_posts = Column(Integer, default=0, nullable=False)
    total_recruits = Column(Integer, default=0, nullable=False)
    score_unresolved = Column(Integer, default=0, nullable=False)
    evidence_level = Column(String(32), default="verified")
    status = Column(String(32), default="verified")
    snapshot_date = Column(String(32))
    gaps = Column(Text, default='[]')
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<Cycle {self.cycle}>"
