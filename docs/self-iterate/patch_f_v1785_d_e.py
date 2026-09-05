# -*- coding: utf-8 -*-
"""v17.8.5 阶段 D+E：release.json 版本单源 + verifier 语义不变式 + 前端去 PHANTOM_CODES"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "网站"
TPL = ROOT / "项目源码" / "tools" / "anhui_web" / "templates"
LITE = ROOT / "网站-lite"

RELEASE = {"schema": "wanyu-release/v1", "release": "v17.8.5", "asset_version": "17.8.5",
           "service_worker_version": "wanyu-shell-v48"}

# ---- D1: release.json 唯一版本源 ----
(ROOT / "项目源码" / "release.json").write_text(json.dumps(RELEASE, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("OK release.json")

# ---- D2: build_maintainable_site.py / release.py 从 release.json 取版本 ----
p = ROOT / "项目源码" / "tools" / "anhui_web" / "build_maintainable_site.py"
t = p.read_text(encoding="utf-8")
old = 'RELEASE = "v17.7.1"'
new = '''# D(2026-09-05): 版本唯一真源 = 项目源码/release.json，禁止此处硬编码
RELEASE = json.loads((Path(__file__).resolve().parents[2] / "release.json").read_text(encoding="utf-8"))["release"]'''
assert t.count(old) == 1
p.write_bytes(t.replace(old, new).encode("utf-8"))

p = ROOT / "项目源码" / "tools" / "anhui_web" / "release.py"
t = p.read_text(encoding="utf-8")
old = 'BUILD_VERSION = "v17.7.1"'
new = '''# D(2026-09-05): 版本唯一真源 = 项目源码/release.json
BUILD_VERSION = json.loads((Path(__file__).resolve().parents[2] / "release.json").read_text(encoding="utf-8"))["release"]'''
assert t.count(old) == 1, t.count(old)
p.write_bytes(t.replace(old, new).encode("utf-8"))
print("OK builder/release 读 release.json")

# ---- D3: 站点与模板升到 v17.8.5 / SW v48 ----
for f in (SITE / "index.html", SITE / "sw.js"):
    t = f.read_text(encoding="utf-8")
    n = t.count("17.8.4")
    assert n >= 12, (f, n)
    f.write_bytes(t.replace("17.8.4", "17.8.5").replace("wanyu-shell-v47", "wanyu-shell-v48").encode("utf-8"))
import shutil
shutil.copy(SITE / "sw.js", TPL / "maintainable-sw.js")
for f in ("index.html", "sw.js"):
    shutil.copy(SITE / f, LITE / f)
mp = SITE / "data" / "site-manifest.json"
m = json.loads(mp.read_text(encoding="utf-8"))
m["release"] = "v17.8.5"
# C6: 逐周期 raw/active/excluded 记入 manifest
for c in m["cycles"]:
    y = str(c["cycle"])
    if y == "2026":
        c["raw_posts"], c["active_posts"], c["excluded_posts"] = 8511, 8401, 110
    else:
        c["raw_posts"] = c["active_posts"] = c.get("posts")
        c["excluded_posts"] = 0
mp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
print("OK 站点/模板/manifest → v17.8.5 / v48")

# ---- C5: 前端去 PHANTOM_CODES，改 record_status 过滤 ----
FILES = (SITE / "assets" / "maintainable-site.js", TPL / "maintainable-site.js", LITE / "assets" / "maintainable-site.js")
old_block_start = "// D2(2026-09-05): 马鞍山 110 个疑似重复收录岗位"
for f in FILES:
    t = f.read_text(encoding="utf-8")
    start = t.find(old_block_start)
    assert start != -1, f
    end = t.find("const rowsFor", start)
    assert end != -1
    t = t[:start] + """// record_status 生命周期（wanyu-record-status/v1）：用户产品统计只认 active；排除记录保留在数据层供审计
  const isActiveRow = (row) => !row || !row.record_status || row.record_status === "active";
  """ + t[end:]
    old_rf = "const rowsFor = (payload) => Array.isArray(payload?.allMajors?.rows) ? payload.allMajors.rows.filter((row) => !isPhantomRow(row)) : [];"
    new_rf = "const rowsFor = (payload) => Array.isArray(payload?.allMajors?.rows) ? payload.allMajors.rows.filter(isActiveRow) : [];"
    assert t.count(old_rf) == 1, f
    t = t.replace(old_rf, new_rf)
    old_pal = ".filter((row) => !isPhantomRow(row)).map"
    new_pal = ".filter(isActiveRow).map"
    assert t.count(old_pal) == 1, f
    t = t.replace(old_pal, new_pal)
    f.write_bytes(t.encode("utf-8"))
    print("OK 前端 record_status 过滤", f.name)

# major-index 构建器同口径
p = ROOT / "项目源码" / "tools" / "anhui_web" / "build_major_index.py"
t = p.read_text(encoding="utf-8")
old = '''    phantom = load_json(HERE / "data" / "phantom_codes_2026.json")
    rows = [r for r in rows if not (str(r.get("city")) == "马鞍山" and str(r.get("code")) in set(phantom))]'''
new = '''    rows = [r for r in rows if not r.get("record_status") or r.get("record_status") == "active"]  # record_status 生命周期口径'''
assert t.count(old) == 1
p.write_bytes(t.replace(old, new).encode("utf-8"))
print("OK major-index 构建器 record_status 口径")
print("阶段 D + C5 完成（E 在 verifier 单独补丁）")
