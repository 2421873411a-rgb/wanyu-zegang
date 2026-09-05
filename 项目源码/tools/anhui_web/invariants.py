# -*- coding: utf-8 -*-
"""生产门禁不变量（v17.8.5-RC3 阶段 B）。

纪律：**任何承担数据一致性/行数/生命周期/版本/哈希职责的校验禁止使用
Python ``assert``**——``python -O`` / ``PYTHONOPTIMIZE=1`` 会把 assert 全部
剥离，门禁会静默失效。一律改为显式异常。

- :class:`BuildInvariantError`：builder / 数据派生层的一致性违约。
- :class:`RecordLifecycleError`：record_status 枚举与证据违约（见 record_lifecycle.py）。
- :func:`require_int`：strict integer parser——missing/None/非数值/NaN 一律 FAIL；
  允许 int、以及十进制数字字符串（"0"/"116"），JSON number 与锁定数据中的既有
  字符串数字形态都被接受，其它形态拒绝。
"""
from __future__ import annotations

import math
from typing import Any


class BuildInvariantError(RuntimeError):
    """构建期数据不变量违约（等价于曾经的 assert，但 -O 下仍然生效）。"""


class RecordLifecycleError(ValueError):
    """record_status 生命周期违约：未知状态、缺失排除证据、overrides 冲突等。"""


def require_int(value: Any, field_name: str, *, allow_str: bool = True) -> int:
    """Strict integer parser：非法输入直接抛错，绝不回退成 0。

    允许：``0``、``116``、``"0"``、``"116"``。
    拒绝：缺失、None、""、"abc"、[]、浮点 NaN/Inf、True/False。
    """
    if value is None:
        raise BuildInvariantError(f"{field_name}: 缺失（禁止静默回退成 0）")
    if isinstance(value, bool):
        raise BuildInvariantError(f"{field_name}: 布尔值不是合法计数（got {value!r}）")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise BuildInvariantError(f"{field_name}: 非整数数值 {value!r}")
        return int(value)
    if allow_str and isinstance(value, str):
        text = value.strip()
        if text and (text.lstrip("-").isdigit() if text.startswith("-") else text.isdigit()):
            return int(text)
        raise BuildInvariantError(f"{field_name}: 非数字字符串 {value!r}")
    if isinstance(value, (list, tuple, dict)):
        raise BuildInvariantError(f"{field_name}: 容器不是合法计数（got {type(value).__name__}）")
    raise BuildInvariantError(f"{field_name}: 非法计数类型 {type(value).__name__}（got {value!r}）")


def require_mapping(value: Any, field_name: str) -> dict:
    if not isinstance(value, dict):
        raise BuildInvariantError(f"{field_name}: 需要 object，实际 {type(value).__name__}")
    return value


def require_list(value: Any, field_name: str) -> list:
    if not isinstance(value, list):
        raise BuildInvariantError(f"{field_name}: 需要 array，实际 {type(value).__name__}")
    return value
