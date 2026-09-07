from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from app.utils.rate_limit import login_limiter, register_limiter
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    pwd_context,
    sha256_hex,
    verify_password,
)
from app.utils.time import utcnow_naive

router = APIRouter()


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


def _issue_session(db: AsyncSession, user: User) -> TokenResponse:
    """签发 access/refresh，并创建新的 refresh family。"""
    family_id = str(uuid4())
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_jwt, jti = create_refresh_token(data={"sub": str(user.id), "family": family_id})
    db.add(RefreshToken(
        user_id=user.id,
        jti=jti,
        family_id=family_id,
        token_hash=sha256_hex(refresh_jwt),
        expires_at=utcnow_naive() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_jwt,
        user=UserResponse.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    if not settings.ALLOW_REGISTRATION:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="注册功能已关闭")

    rl_key = f"{request.client.host if request.client else 'unknown'}:{user_data.email}"
    if not register_limiter.allow(rl_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="尝试过于频繁，请稍后再试")
    register_limiter.hit(rl_key)

    if (await db.execute(select(User).where(User.email == user_data.email))).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该邮箱已被注册")
    if (await db.execute(select(User).where(User.username == user_data.username))).scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该用户名已被使用")

    user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        display_name=user_data.display_name or user_data.username,
        is_admin=False,
    )
    db.add(user)
    await db.flush()
    return _issue_session(db, user)


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    rl_key = f"{request.client.host if request.client else 'unknown'}:{login_data.email}"
    if not login_limiter.allow(rl_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="尝试过于频繁，请稍后再试")

    user = (await db.execute(select(User).where(User.email == login_data.email))).scalar_one_or_none()
    if not user or not verify_password(login_data.password, user.password_hash):
        login_limiter.hit(rl_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    if not user.is_active:
        login_limiter.hit(rl_key)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户已被禁用")

    login_limiter.clear(rl_key)
    user.last_login_at = utcnow_naive()
    if pwd_context.needs_update(user.password_hash):
        user.password_hash = get_password_hash(login_data.password)
    return _issue_session(db, user)


async def _rotate_refresh(db: AsyncSession, presented: str) -> TokenResponse:
    payload = decode_token(presented)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")

    token_hash = sha256_hex(presented)
    record = (await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    )).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")

    now = utcnow_naive()
    if record.is_revoked:
        family = await db.execute(select(RefreshToken).where(
            RefreshToken.user_id == record.user_id,
            RefreshToken.family_id == record.family_id,
            RefreshToken.revoked_at.is_(None),
        ))
        for sibling in family.scalars().all():
            sibling.revoked_at = now
        # 必须先提交 family revoke，再返回 401；否则依赖层 rollback 会丢掉安全动作。
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌已被使用，请重新登录")

    if record.expires_at and record.expires_at < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌已过期")

    user_id = payload.get("sub")
    if str(record.user_id) != str(user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已被禁用")

    record.revoked_at = now
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_jwt, jti = create_refresh_token(data={"sub": str(user.id), "family": record.family_id})
    db.add(RefreshToken(
        user_id=user.id,
        jti=jti,
        family_id=record.family_id,
        token_hash=sha256_hex(refresh_jwt),
        expires_at=now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_jwt,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await _rotate_refresh(db, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)):
    token_hash = sha256_hex(body.refresh_token)
    record = (await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )).scalar_one_or_none()
    if record and not record.is_revoked:
        family = await db.execute(select(RefreshToken).where(
            RefreshToken.user_id == record.user_id,
            RefreshToken.family_id == record.family_id,
            RefreshToken.revoked_at.is_(None),
        ))
        now = utcnow_naive()
        for sibling in family.scalars().all():
            sibling.revoked_at = now
    return None


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
