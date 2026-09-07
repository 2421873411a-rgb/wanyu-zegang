import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.time import utcnow_naive


class FilterSnapshot(Base):
    __tablename__ = "filter_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cycle = Column(String(8), nullable=False)
    view = Column(String(32), nullable=False)
    filters = Column(Text, default="{}")
    metric = Column(String(32), default="jobs")
    release = Column(String(32), default="")
    created_at = Column(DateTime(timezone=False), default=utcnow_naive, nullable=False)

    user = relationship("User", back_populates="filter_snapshots")

    def __repr__(self):
        return f"<FilterSnapshot {self.view}>"
