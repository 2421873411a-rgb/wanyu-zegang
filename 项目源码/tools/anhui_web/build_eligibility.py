# -*- coding: utf-8 -*-
"""把外部核验到的职位表资格字段合并为 position_eligibility.json。

数据来源（2026-08-28 核查会话产出）：
- _web/huatu_sy.json            事业单位 132 条华图职位库详情（备注/学历/专业）
- 省考备注核查结果.json          省考 406 条省考职位表"其他/经历要求/政治面貌"
- data/job_eligibility_exclusions.json  当前身份定向核除清单（官方复核项不再混入用户标记）

产物：data/position_eligibility.json，代码 → {kind, remark, other, experience, face,
xueli, zhuanye, tags, source_url, note}。tags 是结构化身份标签，供页面画像引擎判定。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WEB = ROOT / "_web"


def classify(text: str, code: str = "") -> list[str]:
    tags: list[str] = []
    if re.search(r"服务基层项目|三支一扶|大学生村官|西部计划|特岗教师", text):
        tags.append("four_project")
    if "随军家属" in text:
        tags.append("military_family")
    if ("退役士兵" in text) or ("定向" in text and "退役" in text):
        tags.append("veteran")
    if re.search(r"定向", text) and not tags:
        tags.append("targeted")
    if re.search(r"(?<!非)应届(?:高校)?毕业生", text) and "服务期满" not in text:
        tags.append("fresh_only")
    if re.search(r"限男性|适合男性|仅限男性", text):
        tags.append("gender_male")
    if re.search(r"限女性", text):
        tags.append("gender_female")
    if "中共党员" in text:
        tags.append("party")
    if "法律职业资格" in text:
        tags.append("cert_legal")
    if "最低服务期" in text:
        tags.append("min_service")
    if "差额补贴" in text:
        tags.append("allowance_diff")
    if re.search(r"值夜班|夜间执法|24小时值班", text):
        tags.append("night_shift")
    if "专业测试" in text:
        tags.append("prof_test")
    return tags


def main() -> None:
    out: dict[str, dict] = {}
    sy_cache = json.loads((WEB / "huatu_sy.json").read_text(encoding="utf-8")) if (WEB / "huatu_sy.json").exists() else {}
    gwy_rows = json.loads((ROOT / "省考备注核查结果.json").read_text(encoding="utf-8")) if (ROOT / "省考备注核查结果.json").exists() else []
    guokao_payload = json.loads((HERE / "data" / "guokao2026.json").read_text(encoding="utf-8")) if (HERE / "data" / "guokao2026.json").exists() else {}
    guokao_rows = {str(row.get("code") or "").strip(): row for row in guokao_payload.get("positions", [])}
    exclusions = json.loads((HERE / "data" / "job_eligibility_exclusions.json").read_text(encoding="utf-8"))["exclusions"]

    for code, entry in sy_cache.items():
        if entry.get("status") != "ok":
            continue
        remark = (entry.get("remark") or "").strip()
        other = ""
        out[code] = {
            "kind": "sydw",
            "remark": remark,
            "other": other,
            "xueli": (entry.get("xueli") or "").strip(),
            "zhuanye": (entry.get("zhuanye") or "").strip(),
            "source_url": entry.get("url") or "",
        }

    for row in gwy_rows:
        code = str(row.get("code") or "")
        if not code or row.get("status") != "ok":
            continue
        other = "；".join(x for x in (row.get("other"), row.get("experience"), row.get("face")) if x)
        out[code] = {
            "kind": "gwy",
            "remark": (row.get("remark") or "").strip(),
            "other": other,
            "source_url": "",
        }

    gk_source_file = "source_data/anhui2026/raw/2026guokao_anhui.xlsx"
    for code in ("300110013003", "300147355001", "300147357001"):
        source_row = guokao_rows.get(code)
        out.setdefault(code, {"kind": "gk", "remark": "", "other": "", "note": "国考岗位未核验备注"})
        if source_row:
            out[code].update({
                "remark": str(source_row.get("official_remark") or "").strip(),
                "note": "国考 2026 安徽官方职位表备注",
                "source_file": gk_source_file,
            })

    for code, item in out.items():
        text = "；".join(str(item.get(k) or "") for k in ("remark", "other"))
        if code in exclusions:
            text += "；" + str(exclusions[code].get("source_remark") or "")
            item["source_url"] = item.get("source_url") or exclusions[code].get("source_url") or ""
            if exclusions[code].get("category") == "user_flagged":
                item["note"] = "用户标记四项目定向岗，待官方岗位表复核"
        item["tags"] = classify(text, code)
        item = out[code]

    payload = {
        "version": 1,
        "updated": "2026-08-28",
        "tag_labels": {
            "four_project": "四项目定向",
            "veteran": "退役士兵定向",
            "military_family": "随军家属定向",
            "targeted": "其他定向",
            "fresh_only": "仅应届",
            "gender_male": "限男性",
            "gender_female": "限女性",
            "party": "中共党员",
            "cert_legal": "法律职业资格",
            "min_service": "最低服务期",
            "allowance_diff": "差额补贴",
            "night_shift": "夜班/值班",
            "prof_test": "专业测试",
        },
        "profile_keys": {
            "four_project": "我是“服务基层项目”人员（四项目）",
            "veteran": "我是退役士兵",
            "military_family": "我是随军家属",
            "fresh": "我是应届毕业生（含择业期内）",
            "male": "男性",
            "female": "女性",
            "party": "我是中共党员",
            "cert_legal": "我有法律职业资格证",
        },
        "positions": out,
    }
    target = HERE / "data" / "position_eligibility.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    tagged = sum(1 for v in out.values() if v["tags"])
    print(f"positions={len(out)} tagged={tagged} -> {target}")


if __name__ == "__main__":
    main()
