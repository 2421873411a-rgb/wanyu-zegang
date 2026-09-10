import hashlib
from datetime import timedelta
from typing import Optional, Tuple
from uuid import uuid4

import jwt
from passlib.context import CryptContext
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.utils.time import utcnow_naive


# 密码哈希上下文
# bcrypt_sha256 用 SHA-256 预处理解决 bcrypt 72 字节截断；保留 bcrypt 兼容旧 $2b$。
pwd_context = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated=["bcrypt"])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """bcrypt 是纯 CPU 工作，绝不能直接占 async 事件循环（v17.10.2 P1-05）。"""
    return await run_in_threadpool(verify_password, plain_password, hashed_password)


async def get_password_hash_async(password: str) -> str:
    return await run_in_threadpool(get_password_hash, password)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = utcnow_naive() + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> Tuple[str, str]:
    to_encode = data.copy()
    jti = str(uuid4())
    expire = utcnow_naive() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "jti": jti})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt, jti


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except (jwt.exceptions.PyJWTError, jwt.exceptions.DecodeError, jwt.exceptions.ExpiredSignatureError):
        return None
