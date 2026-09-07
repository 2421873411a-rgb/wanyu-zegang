# Round 1 审计报告 · 镜头：版本文档一致性（子代理产出，主控抽查证实）

- V1 P1 APP_VERSION 三处矛盾（config.py:16=v17.9.0 / .env.example:5=1.0.0 / main=v17.9.10），十次发布未 bump。**证实**
- V2 P1 /health 无版本字段（main.py:57-60）+ deploy smoke 无版本断言 → 部署后无法证明新版本生效。**证实**
- V3 P1 record_status 词表三方冲突：record_lifecycle.py:25 ALLOWED=active+{duplicate,invalid_source,withdrawn,superseded,needs_review}（契约 docs/data-contract/record-status.md 同）；import_service.py:46 白名单={None,"",active,duplicate,excluded}。契约合法的 withdrawn/superseded/invalid_source/needs_review 行会令 API 整包 fail-closed 拒绝；DB 层 'excluded' 状态无契约文档。**证实**
- V4 P2 CONTRACT.md 三处过期（版本头 / allMajors-only 声明 / skipped 对账公式）
- V5 P2 README 导入示例断链（import_cycle_jobs/load_json_file 已不存在）、用例数 21 vs 实际 37
- V6 P2 版本历史三断链：tag 停 v17.9.0、CHANGELOG 停 v16.2.1、交接包说明停 v17.8.6+b1
- V7 P2 =0.4.0（pip 事故产物）与 requirements-dev.in（僵尸声明，约束链还和已跟踪 .txt 不同）——均 untracked
- V8 P2 test_v17_salary_and_motion.py:122 自身硬编码 v17.9.0（注释刚说完禁止硬编码）；且不在任何 CI 测试列表
- V9 P2 .gitignore 宣告忽略 deliverables/ 但 CHANGELOG.md 等仍被跟踪
- V10 已验证无问题（重要基线）：**网站资产链自洽**——release.json(v17.9.0)=site-manifest=index.html ?v=17.9.0=sw.js wanyu-shell-v50，且 `git diff v17.9.0..main -- 网站` 为空 → release.json 对「网站产品」不算错，漂移在 API 侧与项目级叙事；metrics 不变式、README 路由表、限流文档均与实现一致
