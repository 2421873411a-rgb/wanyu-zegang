# Round 1 Triage 与修复计划（v17.9.11）

## Triage 结论：P0×1、P1×8 全部确认；P2 确认 18、豁免 3、驳回 0

四镜头审计（部署链/数据完整性/CI 真实性/版本文档）共产出 30 条发现。主控逐条对照源码行号/复现证实，
无驳回项。豁免（书面理由）：
- D7 xl 归一漂移 → 豁免+文档化：DB 镜像 canonical 真源（原始口径），静态 xl 归一是表现层约定；
  生产导入走静态路径口径稳定；CONTRACT.md 明确 canonical 为权威、归一为表现层。
- D11 review-queue 无鉴权 → 豁免+文档化：同一数据由静态站 `data/audit/review-queue.json` 公开，属设计公开面，
  API 只是镜像；收紧 API 不改变暴露面。
- C4 零 PR 审批 → 豁免：单人仓库；三 required check + enforce_admins 已是实际门禁。

## 修复批次（分支 fix/v17.9.11-round1-hardening，基线 origin/main=8cdc38e）

### A 部署链（F1-F11）
- A1 P0 LOG_DIR/PID_DIR chown www-data:750；删无用 PID_DIR
- A2 P1 pg_get_userby → pg_get_userbyid
- A3 P1 nginx alias→root；smoke 增 /maintainable/index.html 200 + http→https 跳转断言
- A4 certbot --redirect
- A5 载荷确定性：cd 脚本目录 + tar 排除清单（.git/.venv/venv/__pycache__/垃圾文件）
- A6 最小回滚脚手架：旧版本代码备份 + alembic 版本戳 + RUNBOOK（软链架构留 S8 实测后再上）
- A7 create_admin 入链（env 传参可选执行 + 完成横幅）
- A8 apt 补 curl/sudo + command -v 前置断言；去 :142 || true；.env 写 $STATIC_DATA_PATH 实值
- A9 runtime lock 补 uvloop（Linux extra 完备性）
- A10 linkage 测试扩面：worker_class 断言、lock 必含 gunicorn/alembic/uvicorn-worker/uvloop、
  unit/nginx 模板关键行断言、deploy.sh 含 pg_get_userbyid、health 版本断言

### B 数据/API 完整性（D1-D12 + V3）
- B1 P1 canonical schema 文档（含 all_majors 键）强制 provenance.job_id_set_sha256，缺失即拒
- B2 P1 review events 幂等 upsert（kind+cycle+title）
- B3 P1 收藏/对比 add 时校验 active Job 存在且 cycle 匹配（400）；snapshot_replace 对 stale 级联清理引用
- B4 Job 增 exclusion_reason/evidence/excluded_at 三列 + migration 0003 + 导入/stale 双路径写入
- B5 meta 口径配对强制（total/recruits 必须同为 raw 或同为 active，拒绝混搭）
- B6 num/bm 拒绝非整数浮点
- B7 Cycle.snapshot_date 从 label/meta 回填
- B8 mirror_state upsert 去死分支（无条件 setattr）
- B9 dashboard 双口径（active+excluded 计数）
- B10 导入响应附全周期 mirror_state 摘要（跨周期版本错位可见）
- B11 V3 record_status 词表对齐契约：白名单 +{invalid_source,withdrawn,superseded,needs_review}
  （DB 仍折叠二值）；record-status.md 补 DB 层折叠与 'excluded' 派生态文档
- 测试：每项先红后绿（PG 并发相关进 PG 专属文件）

### C CI + 版本文档（C1/C2/C5 + V1-V9）
- C1 P1 canonical-ci 改 discovery 循环：20 个 py 模块自动入门禁 + EXCLUDED 清单（10 模块，附产物依赖理由）
  + 4 个 .cjs 模块 node --test（setup-node）；新增护栏：发现未登记模块即红（fail-closed 双向）
- C2 P1 wan-api-ci 增真数据 e2e 步骤（scripts/e2e_real_data.py：6 快照校验+临时库导入+幂等+对账）
  + dev lock pip-audit --strict
- C5 concurrency main 豁免（两 workflow）
- C6 V1 APP_VERSION 单一真源：config 启动读 release.json；.env.example 移除该字段；linkage 测试锁一致性
- C7 V2 /health 返回 version；deploy smoke 断言版本==release.json
- C8 V4/V5 CONTRACT.md 导入纪律重写（v17.9.11 头、双键、二值折叠、deactivated 对账）+ README 示例/用例数修复
- C9 V6 CHANGELOG 补 v17.9.1→v17.9.11；tag v17.9.10（追溯）与 v17.9.11（合并后）
- C10 V7/V9 删 =0.4.0 与 requirements-dev.in；.gitignore 移除 deliverables/ 规则（正式收编）
- C11 V8 test_v17_salary_and_motion 硬编码版本改一致性断言（入 discovery 集）
- C12 D10 部分修复并入 B10
- 合并后：C3 branch protection 将 canonical check 重绑 GitHub Actions app（API 操作+验证）

## 验证与收口
- 本地九门全绿 + CI 模拟（git archive checkout）下新 canonical 测试集全绿
- PR 三 required 全绿（查日志）→ merge → tag v17.9.11 → C3 重绑 → Round 2 审计
