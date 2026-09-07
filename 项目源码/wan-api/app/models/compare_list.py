import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class CompareList(Base):
    """用户对比列表模型"""
    __tablename__ = "compare_lists"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    record_id = Column(String(128), nullable=False)
    cycle = Column(String(8), nullable=False)
    position = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # v17.9.1 S1：应用层 check-then-insert 在并发下有竞态，数据库层唯一约束兜底
    __table_args__ = (
        UniqueConstraint("user_id", "record_id", name="uq_compare_user_record"),
    )
    
    # 关系
    user = relationship("User", back_populates="compare_lists")
    
    def __repr__(self):
        return f"<CompareList {self.record_id}>"
