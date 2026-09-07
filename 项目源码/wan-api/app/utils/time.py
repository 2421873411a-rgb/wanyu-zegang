"""UTC 时间辅助。

数据库历史 schema 使用 `TIMESTAMP WITHOUT TIME ZONE`，因此统一写入“UTC 语义的 naive datetime”。
避免 Python 3.12+ 已弃用的 `datetime.utcnow()`，同时不改变现有列类型/比较语义。
"""
from datetime import UTC, datetime


def utcnow_naive() -> datetime:
    """返回去掉 tzinfo 的当前 UTC 时间，保持现有数据库 DateTime(timezone=False) 契约。"""
    return datetime.now(UTC).replace(tzinfo=None)
