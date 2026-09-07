from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base
from app.utils.time import utcnow_naive


class ReviewEvent(Base):
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
    created_at = Column(DateTime(timezone=False), default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=utcnow_naive, onupdate=utcnow_naive, nullable=False)

    def __repr__(self):
        return f"<ReviewEvent {self.kind}>"
