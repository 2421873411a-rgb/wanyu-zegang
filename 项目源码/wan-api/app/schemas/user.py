import re

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime


_USERNAME_PATTERN = re.compile(r"^[\w一-鿿.-]{2,64}$")


class UserCreate(BaseModel):
    """用户注册请求"""
    email: EmailStr
    username: str = Field(min_length=2, max_length=64)

    @field_validator("username")
    @classmethod
    def username_charset(cls, v: str) -> str:
        # 审计 F-018：禁空白/控制字符/同形混淆字符；字母数字下划线汉字点连字符
        v = v.strip()
        if not _USERNAME_PATTERN.fullmatch(v):
            raise ValueError("用户名仅支持汉字、字母、数字、下划线、点和连字符（2~64 位）")
        return v
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
    # 登录密码与注册同上限：超长直接 422，不进 bcrypt（匿名可达面资源边界）
    password: str = Field(min_length=1, max_length=128)


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
