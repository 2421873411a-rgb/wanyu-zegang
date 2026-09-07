"""Refresh Token 服务器端状态（v17.9.1 S2）。

设计：refresh JWT 仍签名（纵深防御），但真正凭证是库里的 hash 记录——
- jti + family_id：轮换链路可追踪
- token_hash：库里只存 sha256，不存原文
- revoked_at：轮换即撤销旧 token；已撤销 token 再次出现 = 重用攻击 → 撤销整个 family
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from app.database import Base


class RefreshToken(Base):
    """刷新令牌（服务器端状态，支撑轮换/撤销/重用检测）"""
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    jti = Column(String(36), nullable=False, unique=True)
    family_id = Column(String(36), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=False), nullable=False)
    revoked_at = Column(DateTime(timezone=False))
    created_at = Column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_refresh_tokens_user_family", "user_id", "family_id"),
    )

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def __repr__(self):
        return f"<RefreshToken jti={self.jti} family={self.family_id}>"
