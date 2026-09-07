# Round 1 审计报告 · 镜头：CI 门禁真实性（子代理产出，含 run 日志与 branch protection API 实证）

- C1 P1 canonical required check 只跑 5 个白名单模块（run 34118739203 'Ran 26 tests'），~30 个活跃测试模块（test_v17_salary_and_motion、test_release_integrity、test_frontend_data_audit 等，git log 证实近期仍在改动）在任何 CI 门禁之外；.cjs node 测试无 node 环境。
- C2 P1 §10 门8（真数据 e2e）与门5后半（dev lock pip-audit）不在 CI：破坏导入幂等/真数据契约的 PR 可三门全绿合入；dev 依赖 CVE 零审计。
- C3 P2 required check 'canonical' app_id=null（test/postgres=15368），可被持有 status 写权限的 token 用同名 commit status 顶替——防伪链在此断。
- C4 P2 required_approving_review_count=0（单人仓库取舍，见 triage 豁免）。
- C5 P2 concurrency cancel-in-progress 无 main 豁免：快速连续 merge 可使 main 提交无自身完成的绿 run。
- C6 已验证无问题（重要基线）：paths-filter 已彻底移除、无 workflow_run、无 paths 过滤、required check 名与 job id 严格匹配、三门真实执行基线吻合（35+2/37/init_db PASS/pip-audit clean/canonical PASS/26 tests）、零吞错、cache 绑锁文件哈希、token 最小化、enforce_admins+禁 force push。
