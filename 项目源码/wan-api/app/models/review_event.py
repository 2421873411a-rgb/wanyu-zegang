from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime
from app.database import Base


class ReviewEvent(Base):
    """审计事件模型"""
    __tablename__ = "review_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, default="medium", index=True)
    cycle = Column(String(8))
    title = Column(String(512))
    detail = Column(Text)
    evidence = Column(Text)
    occurrences = Column(Integer, default=1)
    resolution_trigger = Column(Text)
    status = Column(String(32), default="open")
    created_at = Column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<ReviewEvent {self.kind}>"
