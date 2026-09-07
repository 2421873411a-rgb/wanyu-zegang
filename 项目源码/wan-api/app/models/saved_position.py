import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class SavedPosition(Base):
    """用户收藏岗位模型"""
    __tablename__ = "saved_positions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    record_id = Column(String(128), nullable=False)
    cycle = Column(String(8), nullable=False)
    note = Column(String(500), default="")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # v17.9.1 S1：并发收藏竞态由数据库唯一约束兜底
    __table_args__ = (
        UniqueConstraint("user_id", "record_id", name="uq_saved_user_record"),
    )
    
    # 关系
    user = relationship("User", back_populates="saved_positions")
    
    def __repr__(self):
        return f"<SavedPosition {self.record_id}>"
