sources.lock 完整校验通过：14 项全部一致（文件 sha256 + 目录 rollup）
canonical 验证： {"2024": {"raw_posts": 10017, "active_posts": 10017, "excluded_posts": 0, "raw_recruits": 15331, "recruits": 15331}, "2025": {"raw_posts": 10150, "active_posts": 10150, "excluded_posts": 0, "raw_recruits": 14721, "recruits": 14721}, "2026": {"raw_posts": 8511, "active_posts": 8401, "excluded_posts": 110, "raw_recruits": 12006, "recruits": 11883}}
validate_canonical: PASS（schema + 守恒 + 溯源 + score_state + 2026 回归锁定）
audit --check: 重算与已提交工件一致；54 passed, 0 failed
gz built: 54 new, 0 fresh | text payload 105.7MB -> 9.8MB gz (91% saved)
maintainable: 302 passed, 0 failed
scope                                raw          gzip        budget  status
2024/audit                         6,398         1,934        40,000  OK
2024/catalog                   4,122,556       420,130       780,000  OK
2024/changes                         282           207     3,000,000  OK
2024/derived                       2,441           975        20,000  OK
2024/jobs                     12,055,607       874,058     1,350,000  OK
2024/jobs_lite                 8,294,940       682,668       780,000  OK
2024/major_city                  543,883        57,288        80,000  OK
2024/major_index               1,481,131       386,988             —  OK
2024/overview                      4,543         2,090        40,000  OK
2024/positions                 6,080,178       489,981       660,000  OK
2025/audit                         7,972         2,274        40,000  OK
2025/catalog                   4,681,380       482,568       780,000  OK
2025/changes                   2,539,769       293,554     3,000,000  OK
2025/derived                       2,443           989        20,000  OK
2025/jobs                     12,983,040       950,380     1,350,000  OK
2025/jobs_lite                 8,816,563       709,672       780,000  OK
2025/major_city                  547,845        57,976        80,000  OK
2025/major_index               1,840,072       448,888             —  OK
2025/overview                      4,507         1,985        40,000  OK
2025/positions                 6,226,428       511,365       660,000  OK
2026/audit                         4,342         1,783        40,000  OK
2026/catalog                   3,959,658       397,984       780,000  OK
2026/changes                   2,299,681       264,338     3,000,000  OK
2026/derived                       2,448           984        20,000  OK
2026/jobs                     11,053,894       900,931     1,350,000  OK
2026/jobs_lite                 7,259,667       620,634       780,000  OK
2026/major_city                  487,851        50,561        80,000  OK
2026/major_index               1,553,251       379,523             —  OK
2026/overview                      1,577           902        40,000  OK
2026/positions                 5,215,743       439,819       660,000  OK
2026/req_fields                2,759,264       135,316             —  OK
global/map                        65,678        22,153        40,000  OK
global/salary                      3,232         1,149        40,000  OK
global/audit                      15,628         3,649        40,000  OK
global/review_queue                4,440         1,135        20,000  OK
global/job_history               392,307        53,885       120,000  OK
global/supplement                 29,559         5,464        50,000  OK

合计 gzip ≈ 9.7 MB · 模块 37 个 · 超预算 0 项
maintainable browser walkthrough: PASS (three cycles, ranking major filter, search, boundary, responsive)
major_city browser smoke: PASS (fast path, fallback, responsive)
ui upgrade browser smoke: PASS (search rail, mobile nav, more drawer, detail drawer, exam batches)
clean rebuild = 流水线（promote=False）→ C:\Users\24218\AppData\Local\Temp\wanyu-clean-rebuild-ovzypo1h
[pipeline 2/8] verify_sources（锁只读）
$ C:\Users\24218\AppData\Local\Programs\Python\Python311\python.exe verify_sources.py
[pipeline 3/8] validate_canonical
$ C:\Users\24218\AppData\Local\Programs\Python\Python311\python.exe tools/anhui_web/validate_canonical.py --root .
[pipeline 4/8] audit --check（只读复核）
$ C:\Users\24218\AppData\Local\Programs\Python\Python311\python.exe tools/anhui_web/audit_three_years.py --root . --output-json tools/anhui_web/data/three_year_audit.json --check
[pipeline 5/8] build → C:\Users\24218\AppData\Local\Temp\wanyu-clean-rebuild-ovzypo1h
$ C:\Users\24218\AppData\Local\Programs\Python\Python311\python.exe tools/anhui_web/build_gz.py C:\Users\24218\AppData\Local\Temp\wanyu-clean-rebuild-ovzypo1h
[pipeline 6/8] 受锁输入前后一致：9 files → verify_site
$ C:\Users\24218\AppData\Local\Programs\Python\Python311\python.exe tools/anhui_web/verify_maintainable_site.py C:\Users\24218\AppData\Local\Temp\wanyu-clean-rebuild-ovzypo1h
$ C:\Users\24218\AppData\Local\Programs\Python\Python311\python.exe tools/anhui_web/perf_budget.py C:\Users\24218\AppData\Local\Temp\wanyu-clean-rebuild-ovzypo1h
asset parity → 13 files, help/changelog markers present
[pipeline 7/8] browser smoke ×3（WANYU_SITE_DIR → staging）
$ node tests/maintainable_browser_smoke.js (WANYU_SITE_DIR=C:\Users\24218\AppData\Local\Temp\wanyu-clean-rebuild-ovzypo1h)
$ node tests/major_city_browser_smoke.cjs (WANYU_SITE_DIR=C:\Users\24218\AppData\Local\Temp\wanyu-clean-rebuild-ovzypo1h)
$ node tests/ui_upgrade_browser_smoke.cjs (WANYU_SITE_DIR=C:\Users\24218\AppData\Local\Temp\wanyu-clean-rebuild-ovzypo1h)
2026 锁定事实： {'raw_posts': 8511, 'active_posts': 8401, 'excluded_posts': 110, 'raw_recruits': 12006, 'recruits': 11883, 'lite_rows': 8401, 'score_unresolved': 0, 'resolved': 116}
注意：tmp 产物与 网站 的字节差异仅允许来自 runtime source_file（canonical 引用名）等装配元数据；
如需同步生产，请执行发布流水线（release.py：staging → 原子提升）而非手工拷贝。
CLEAN_REBUILD_EXIT=0
