"""Mirror State 模型（P1-3：追踪 DB 镜像的是哪版 canonical）"""
import uuid

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base
from app.utils.time import utcnow_naive


class MirrorState(Base):
    """周期级镜像状态：记录 DB 当前镜像的 canonical 版本和哈希。"""
    __tablename__ = "mirror_state"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cycle = Column(String(8), unique=True, nullable=False, index=True)
    release = Column(String(64), default='')
    source_sha256 = Column(String(64), default='')
    job_id_set_sha256 = Column(String(64), default='')
    source_rows = Column(Integer, default=0)
    active_rows = Column(Integer, default=0)
    recruits = Column(Integer, default=0)
    imported_at = Column(DateTime(timezone=False), default=utcnow_naive, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=utcnow_naive, onupdate=utcnow_naive, nullable=False)

    def __repr__(self):
        return f"<MirrorState cycle={self.cycle} release={self.release}>"
