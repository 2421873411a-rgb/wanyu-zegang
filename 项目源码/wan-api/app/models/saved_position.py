import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.time import utcnow_naive


class SavedPosition(Base):
    __tablename__ = "saved_positions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    record_id = Column(String(128), nullable=False)
    cycle = Column(String(8), nullable=False)
    note = Column(String(500), default="")
    created_at = Column(DateTime(timezone=False), default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=utcnow_naive, onupdate=utcnow_naive, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "record_id", name="uq_saved_user_record"),)
    user = relationship("User", back_populates="saved_positions")

    def __repr__(self):
        return f"<SavedPosition {self.record_id}>"
