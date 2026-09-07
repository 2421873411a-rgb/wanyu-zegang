import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import uuid4

import jwt
from passlib.context import CryptContext
from app.config import settings


# 密码哈希上下文
# P2-bcrypt：bcrypt_sha256 用 SHA-256 预处理解决 72 字节截断。
# 保留 bcrypt 作为已弃用方案——旧库中已有的 $2b$ hash 仍可验证，
# 登录成功后自动 rehash 为 bcrypt_sha256。
pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated=["bcrypt"])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def sha256_hex(value: str) -> str:
    """凭证指纹：库里只存 hash，不存原文"""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> Tuple[str, str]:
    """创建刷新令牌。

    v17.9.1 S2：携带 jti（服务器端轮换/撤销锚点）；返回 (jwt, jti)。
    family_id 由调用方生成并在同族轮换中保持不变；token 原文的 sha256 由调用方入库。
    """
    to_encode = data.copy()
    jti = str(uuid4())
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "jti": jti})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt, jti


def decode_token(token: str) -> Optional[dict]:
    """解码令牌"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except (jwt.exceptions.PyJWTError, jwt.exceptions.DecodeError, jwt.exceptions.ExpiredSignatureError):
        return None
