from datetime import datetime
from sqlalchemy import Column, String, Integer, Numeric, DateTime, Text
from app.database import Base


class ScoreIndex(Base):
    """成绩索引模型"""
    __tablename__ = "score_index"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cycle = Column(String(8), nullable=False, index=True)
    composite_key = Column(String(256), index=True)
    record_id = Column(String(128))
    scale_id = Column(String(32))
    value = Column(Numeric)
    status = Column(String(32))
    raw_data = Column(Text, default='{}')
    created_at = Column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<ScoreIndex {self.composite_key}>"
