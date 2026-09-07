from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    """用户注册请求"""
    email: EmailStr
    username: str = Field(min_length=2, max_length=64)
    # v17.9.1 S2：密码策略——10~128 位，且必须同时含字母与数字（上限防 bcrypt 截断与 DoS）
    password: str = Field(min_length=10, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("密码必须同时包含字母和数字")
        return v


class UserLogin(BaseModel):
    """用户登录请求"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """用户响应"""
    id: str
    email: str
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_admin: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
