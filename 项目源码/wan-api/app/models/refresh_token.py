"""Refresh Token 服务器端状态。"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, String

from app.database import Base
from app.utils.time import utcnow_naive


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    jti = Column(String(36), nullable=False, unique=True)
    family_id = Column(String(36), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=False), nullable=False)
    revoked_at = Column(DateTime(timezone=False))
    created_at = Column(DateTime(timezone=False), default=utcnow_naive, nullable=False)

    __table_args__ = (Index("ix_refresh_tokens_user_family", "user_id", "family_id"),)

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def __repr__(self):
        return f"<RefreshToken jti={self.jti} family={self.family_id}>"
