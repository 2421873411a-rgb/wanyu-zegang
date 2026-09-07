import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.utils.time import utcnow_naive


class CompareList(Base):
    """用户对比列表：数据库层保证每用户最多四槽。"""
    __tablename__ = "compare_lists"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    record_id = Column(String(128), nullable=False)
    cycle = Column(String(8), nullable=False)
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=False), default=utcnow_naive, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "record_id", name="uq_compare_user_record"),
        UniqueConstraint("user_id", "position", name="uq_compare_user_slot"),
        CheckConstraint("position >= 0 AND position <= 3", name="ck_compare_slot_range"),
    )
    user = relationship("User", back_populates="compare_lists")

    def __repr__(self):
        return f"<CompareList {self.record_id}>"
