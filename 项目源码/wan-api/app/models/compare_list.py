import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, Column, String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class CompareList(Base):
    """用户对比列表模型

    P1-8 四槽约束：position UNIQUE(user_id, position) + CHECK(0..3) 保证并发下永远 ≤4。
    旧方案靠应用层 count 先查再插，并发窗口下可突破上限。
    """
    __tablename__ = "compare_lists"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    record_id = Column(String(128), nullable=False)
    cycle = Column(String(8), nullable=False)
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "record_id", name="uq_compare_user_record"),
        UniqueConstraint("user_id", "position", name="uq_compare_user_slot"),
        CheckConstraint("position >= 0 AND position <= 3", name="ck_compare_slot_range"),
    )
    
    # 关系
    user = relationship("User", back_populates="compare_lists")
    
    def __repr__(self):
        return f"<CompareList {self.record_id}>"
