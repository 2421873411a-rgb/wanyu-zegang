== FINAL SWEEP 2026-09-09 02:23:50 on main=369be13 ==
--- verify_sources --manifest-only ---
sources.lock manifest PASS：14 项结构/路径/哈希格式合法（未声称外部源内容已校验）
EXIT=0
--- verify_sources FULL ---
sources.lock 完整校验通过：14 项全部一致（文件 sha256 + 目录 rollup）
EXIT=0
--- validate_canonical_core ---
canonical core: PASS (schema + conservation + ids + exclusion evidence + reference metadata)
EXIT=0
--- e2e_real_data ---
[e2e] 真数据端到端门禁：PASS
EXIT=0
--- verify_maintainable_site (default→网站/) ---
maintainable: 302 passed, 0 failed
EXIT=0
--- node --test ×4 ---
test_wanyu_core PASS
test_datastore_contract PASS
test_major_city_index PASS
test_user_store_contract PASS
