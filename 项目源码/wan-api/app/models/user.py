import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(128))
    avatar_url = Column(String(512))
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=False), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime(timezone=False))
    
    # 关系
    saved_positions = relationship("SavedPosition", back_populates="user", cascade="all, delete-orphan")
    filter_snapshots = relationship("FilterSnapshot", back_populates="user", cascade="all, delete-orphan")
    compare_lists = relationship("CompareList", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.username}>"
