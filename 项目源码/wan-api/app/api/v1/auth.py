from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse
from app.utils.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, decode_token, sha256_hex,
    pwd_context
)
from app.dependencies import get_current_user
from app.config import settings
from app.utils.rate_limit import login_limiter, register_limiter

router = APIRouter()

# 登录失败限流键前缀（同 IP+账号 5 次失败/5 分钟 → 429）
_LOGIN_WINDOW_SECONDS = 300


class RefreshRequest(BaseModel):
    """刷新请求体。

    v17.9.1 S2：refresh token 一律走 JSON body——
    旧实现用 query 参数，token 会进 nginx/gunicorn 访问日志、代理与浏览器历史。
    """
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


def _issue_session(db: AsyncSession, user: User) -> TokenResponse:
    """签发一对令牌并落库 refresh 状态（新 family）。"""
    family_id = str(uuid4())
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_jwt, jti = create_refresh_token(data={"sub": str(user.id), "family": family_id})
    db.add(RefreshToken(
        user_id=user.id,
        jti=jti,
        family_id=family_id,
        token_hash=sha256_hex(refresh_jwt),
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_jwt,
        user=UserResponse.model_validate(user)
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    """用户注册。

    v17.9.1 S0：注册永远只能创建普通用户。管理员唯一产生路径是
    scripts/create_admin.py（CLI 引导，核对 ADMIN_EMAIL 后人工升权）——
    旧实现 is_admin = (email == ADMIN_EMAIL) 是可抢注的权限模型漏洞。
    """
    if not settings.ALLOW_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="注册功能已关闭"
        )

    rl_key = f"{request.client.host if request.client else 'unknown'}:{user_data.email}"
    if not register_limiter.allow(rl_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="尝试过于频繁，请稍后再试")
    register_limiter.hit(rl_key)

    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册"
        )

    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该用户名已被使用"
        )

    # 创建用户（永远普通用户）
    user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=get_password_hash(user_data.password),
        display_name=user_data.display_name or user_data.username,
        is_admin=False
    )
    db.add(user)
    await db.flush()

    return _issue_session(db, user)


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    """用户登录（IP+账号 双维度失败限流：5 次/5 分钟）"""
    rl_key = f"{request.client.host if request.client else 'unknown'}:{login_data.email}"
    if not login_limiter.allow(rl_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="尝试过于频繁，请稍后再试")

    # 查找用户
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.password_hash):
        login_limiter.hit(rl_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误"
        )

    if not user.is_active:
        login_limiter.hit(rl_key)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用"
        )

    login_limiter.clear(rl_key)

    # 更新最后登录时间
    user.last_login_at = datetime.utcnow()

    # bcrypt 兼容：旧 $2b$ hash 登录成功后自动 rehash 为 bcrypt_sha256
    if pwd_context.needs_update(user.password_hash):
        user.password_hash = get_password_hash(login_data.password)

    return _issue_session(db, user)


async def _rotate_refresh(db: AsyncSession, presented: str) -> TokenResponse:
    """校验并轮换 refresh token；检测到重用即撤销整个 family。"""
    payload = decode_token(presented)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")

    token_hash = sha256_hex(presented)
    # P1-7：FOR UPDATE 锁定行——两个 worker 同时拿同一个 refresh token 时，
    # 后到的 SELECT 会等先到的 UPDATE commit 后再读（已是 revoked → 触发重用检测）。
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    )
    record = result.scalar_one_or_none()

    if record is None:
        # 没有服务器端记录 = 旧体系遗留或伪造 → 一律拒绝
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")

    now = datetime.utcnow()
    if record.is_revoked:
        # 重用检测：已轮换掉的 token 再次出现 → 撤销同族全部令牌
        family = await db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == record.user_id,
                RefreshToken.family_id == record.family_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        for sibling in family.scalars().all():
            sibling.revoked_at = now
        # 先落库再拒绝：撤销动作若留在本次（注定回滚的）事务里会随 raise 丢失
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌已被使用，请重新登录")

    if record.expires_at and record.expires_at < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌已过期")

    user_id = payload.get("sub")
    if str(record.user_id) != str(user_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已被禁用")

    # 轮换：撤销旧 token，签发同族新 token
    record.revoked_at = now
    family_id = record.family_id
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_jwt, jti = create_refresh_token(data={"sub": str(user.id), "family": family_id})
    db.add(RefreshToken(
        user_id=user.id,
        jti=jti,
        family_id=family_id,
        token_hash=sha256_hex(refresh_jwt),
        expires_at=now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    ))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_jwt,
        user=UserResponse.model_validate(user)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """刷新访问令牌（JSON body；旧 query 形态不再接受）"""
    return await _rotate_refresh(db, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)):
    """登出：撤销该 refresh token 所属 family（轮换链一起作废）"""
    payload = decode_token(body.refresh_token)
    token_hash = sha256_hex(body.refresh_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    record = result.scalar_one_or_none()
    if record and not record.is_revoked:
        family = await db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == record.user_id,
                RefreshToken.family_id == record.family_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        now = datetime.utcnow()
        for sibling in family.scalars().all():
            sibling.revoked_at = now
    return None


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserResponse.model_validate(current_user)
