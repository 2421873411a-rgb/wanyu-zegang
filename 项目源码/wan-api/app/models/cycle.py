from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base
from app.utils.time import utcnow_naive


class Cycle(Base):
    __tablename__ = "cycles"

    cycle = Column(String(8), primary_key=True)
    label = Column(String(64), nullable=False)
    total_posts = Column(Integer, default=0, nullable=False)
    total_recruits = Column(Integer, default=0, nullable=False)
    score_unresolved = Column(Integer, default=0, nullable=False)
    evidence_level = Column(String(32), default="verified")
    status = Column(String(32), default="verified")
    snapshot_date = Column(String(32))
    gaps = Column(Text, default="[]")
    created_at = Column(DateTime(timezone=False), default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=utcnow_naive, onupdate=utcnow_naive, nullable=False)

    def __repr__(self):
        return f"<Cycle {self.cycle}>"
