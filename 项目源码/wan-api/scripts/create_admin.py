"""管理员引导脚本（v17.9.1 S0）。

注册接口永远只创建普通用户（消除抢注册路径）；管理员唯一产生路径：
本脚本在服务器上人工执行，核对 ADMIN_EMAIL 后写入。

用法（在 wan-api 目录、虚拟环境内）：
    python scripts/create_admin.py --email admin@kaogong.art --username admin --password '...'
或对已存在用户升权：
    python scripts/create_admin.py --promote admin@kaogong.art

密码来源优先级（v17.10.1）：--password 参数 > 非 tty stdin（部署管道，密码不经
argv/ps 暴露）> 交互 getpass。
"""
import argparse
import asyncio
import getpass
import sys

sys.path.insert(0, ".")

from sqlalchemy import func, select  # noqa: E402
from app.database import async_session_factory, engine, init_db  # noqa: E402
from app.models.user import User  # noqa: E402
from app.utils.security import get_password_hash  # noqa: E402


async def count_active_admins(db) -> int:
    result = await db.execute(select(func.count(User.id)).where(User.is_admin.is_(True), User.is_active.is_(True)))
    return int(result.scalar() or 0)


async def create_admin(email: str, username: str, password: str) -> None:
    async with async_session_factory() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            print(f"拒绝：邮箱 {email} 已存在（如需升权请用 --promote）")
            sys.exit(1)
        user = User(
            email=email,
            username=username,
            password_hash=get_password_hash(password),
            display_name=username,
            is_admin=True,
        )
        db.add(user)
        await db.commit()
        print(f"管理员已创建：{email}（is_admin=True）")


async def promote(email: str) -> None:
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            print(f"拒绝：用户 {email} 不存在（如需新建请用 --email/--username/--password）")
            sys.exit(1)
        user.is_admin = True
        user.is_active = True
        await db.commit()
        admins = await count_active_admins(db)
        print(f"已升权：{email}（当前 active admin 数={admins}）")


def main() -> None:
    parser = argparse.ArgumentParser(description="皖域择岗 API 管理员引导（唯一授权路径）")
    parser.add_argument("--promote", metavar="EMAIL", help="把既有用户升权为管理员")
    parser.add_argument("--email", help="新管理员邮箱")
    parser.add_argument("--username", help="新管理员用户名")
    parser.add_argument("--password", help="新管理员密码（不推荐：argv 经 ps 可见；优先 stdin/交互）")
    args = parser.parse_args()

    if args.promote:
        asyncio.run(promote(args.promote))
        return

    if not args.email or not args.username:
        parser.error("创建管理员需要 --email 与 --username")
    # v17.10.1：stdin 管道优先于交互（deploy.sh bootstrap_admin 走此路径，
    # 密码不再经 argv /proc/cmdline 暴露）；去掉尾部单个换行容忍 heredoc/echo 差异。
    if args.password:
        password = args.password
    elif not sys.stdin.isatty():
        password = sys.stdin.read().rstrip("\r\n")
    else:
        password = getpass.getpass("管理员密码（≥10位，含字母与数字）: ")
    if len(password) < 10 or not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        print("拒绝：密码必须 ≥10 位且同时包含字母与数字")
        sys.exit(1)

    asyncio.run(_init_and_create(args.email, args.username, password))


async def _init_and_create(email: str, username: str, password: str) -> None:
    await init_db()
    try:
        await create_admin(email, username, password)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    main()
