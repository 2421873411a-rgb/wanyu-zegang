# -*- coding: utf-8 -*-
"""城市名归一：源表脏值 → 16 市 + 省直规范集。

规则出处：2024 周期职位表的城市字段存在三种脏值形态（v2 计划 D3a，2026-09-05）——
①「X市」多余后缀（淮南市→淮南）；②市县/市直拼接（六安市直→六安、阜阳界首市→阜阳）；
③省直管县按代管市归属（广德→宣城、宿松→安庆）。
纪律：规范集内的值原样返回；未登记的值原样返回绝不推断——是否登记由人工核对源表后扩充。
"""
from __future__ import annotations

CANONICAL_CITIES = frozenset({
    "合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆",
    "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城", "省直",
})

# 省直管县（县级市/县）由代管地级市归属
_PREFECTURE_OF_COUNTY = {"广德": "宣城", "宿松": "安庆"}


def normalize_source_city(value: object) -> str:
    text = str(value or "").strip()
    if not text or text in CANONICAL_CITIES:
        return text
    stripped = text[:-1] if text.endswith("市") else text
    if stripped in CANONICAL_CITIES:
        return stripped
    if stripped in _PREFECTURE_OF_COUNTY:
        return _PREFECTURE_OF_COUNTY[stripped]
    for city in CANONICAL_CITIES:
        if city != "省直" and text.startswith(city):
            return city
    return text
