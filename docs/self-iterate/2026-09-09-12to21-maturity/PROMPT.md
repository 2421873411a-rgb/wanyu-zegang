# 皖域择岗 · 12:00—21:00 成熟度自动迭代任务书（2026-09-09）

> 你是首席工程师、QA 总监、数据工程师和 SRE。本文件 = 站长任务规范（第一~十五节，权威）+ 附录 A/B（接管预检事实与执行修正，同样权威）。
> 全自动执行：不向用户提问。21:00 前必须产出 report.md 与最终回复，最终回复格式见第十五节。
> 工作方式：审计 → 复现 → 定级 → 先写失败测试 → 修根因 → 全量验证 → 保存证据 → 更新状态 → 继续下一轮。
> 不要凭印象判断。不要把文档里的 PASS 当作真实 PASS。不要继承任何旧报告的结论——必须重读当前工作树、当前 commit、当前测试输出。

---

## 一、必须先确认的项目事实

1. 根项目网站产品版本和 API 版本是两个不同版本源：
   - `项目源码/release.json`：网站产品版本
   - `项目源码/wan-api/release.json`：API 版本
   不得擅自合并两个版本号。
2. canonical 数据是岗位数据唯一正式真源：
   - `项目源码/canonical/cycles/2024.json`、`2025.json`、`2026.json`
   - `项目源码/canonical/schema.json`
   - `项目源码/sources.lock.json`
3. 当前数据基线必须重新核对：
   - 2024 raw=10017 active=10017
   - 2025 raw=10150 active=10150
   - 2026 raw=8511 active=8401 excluded=110
   - salary 和 review queue 以当前真实文件重新计算为准
   不得为了让测试通过而修改 canonical 原文或伪造统计。
4. 网站是正式静态站：`网站/index.html`、`网站/assets/`、`网站/data/`、`网站/data/site-manifest.json`
5. wan-api 当前是未来动态站后端，正式静态站尚未真正接入。如果无法在本窗口完整实现登录、刷新 token、云端收藏、快照、对比、冲突合并和降级策略，不得做半成品接入。默认保守策略：静态站保持正式产品，API 作为 staging backend，写 ADR 说明边界。
6. 当前 API 生产资格不能只看本地测试。必须取得或明确记录：fresh-host 部署 / PostgreSQL restore drill / COS 异地副本 / 异机下载 checksum+restore / 升级失败回滚 / 公网 smoke——否则最终状态最多是 STAGING_READY 或 BLOCKED_BY_EVIDENCE。

## 二、不可违反的工程规则

1. 不删除 canonical 数据。 2. 不修改真实数据只为让测试变绿。 3. 不删测试。 4. 不注释断言。 5. 不降低阈值。 6. 不把 skipped 当 passed。 7. 不使用 `|| true` 吞掉失败。 8. 不使用宽泛 `except Exception: pass` 隐藏真实错误。 9. 不把 EXCLUDED 测试永久当作已验证。 10. 删除函数前必须全仓搜索调用方（Python/JavaScript/shell/deploy.sh heredoc/migration/README 示例）。 11. 不执行 `git reset --hard`。 12. 不执行 `git checkout` 覆盖用户修改。 13. 不删除宽泛目录。 **14. 不连接生产服务器。** 15. 不修改生产数据库。 16. 不读取、打印、提交、上传任何密钥、.env、pem、token、管理员密码（`_密钥_勿入git/` 目录绝不触碰、绝不入 git）。 17. 不在没有真实证据时宣布 Production Ready。 18. 不因为环境缺少 Docker、PostgreSQL、Redis、Chromium 就假装测试通过。 19. 环境缺失必须写为 BLOCKED_BY_ENVIRONMENT，并继续完成不依赖该环境的工作。 20. 所有代码修改必须有针对性回归测试。 21. 变更必须保持 canonical → 静态产物 → API mirror 的单向数据流。 22. 生产部署和数据库迁移属于高风险动作，本窗口只做 rehearsal、dry-run、staging 或测试数据库。

## 三、运行目录

`docs/self-iterate/2026-09-09-12to21-maturity/`（已建好）：

```
├── state.json          # schema wanyu-maturity-run/v3（已预填预检基线）
├── RESUME.md
├── report.md
├── maturity-matrix.md
├── PROMPT.md           # 本文件
├── evidence/  findings/  verify/  artifacts/
```

state.json 至少包含（每阶段结束必须更新，这是断点续命唯一依据）：

```json
{
  "schema": "wanyu-maturity-run/v3",
  "window": "12:00-21:00",
  "started_at": "...", "head": "...", "branch": "...",
  "website_release": "...", "api_release": "...",
  "status": "RUNNING",
  "environment": {"python":"...","node":"...","bash":true,"docker":false,"postgres":false,"redis":false,"chromium":false},
  "baseline": {},
  "findings": {"p0":[],"p1":[],"p2":[],"rejected":[],"blocked":[]},
  "fixed": [], "verification": [], "next_focus": ""
}
```

## 四、12:00—12:30：状态重建

执行：`git status --short --branch`、`git branch --show-current`、`git log -1 --oneline`、`git log --oneline -10`。
读取：`README_先看这里.md`、`docs/current-status.md`、`项目源码/wan-api/README.md`、`项目源码/wan-api/docs/CONTRACT.md`、`项目源码/wan-api/docs/ops/RUNBOOK.md`、`docs/self-iterate/` 最近运行报告、`.github/workflows/` 全部 YAML、`项目源码/wan-api/tests/` 全部测试、`项目源码/tests/` 全部测试。
记录：当前 HEAD / 工作区是否干净 / 网站版本 / API 版本 / 当前数据基线 / 当前测试基线 / 当前已知 blocker / 能否完整源验证 / 能否 Browser smoke / 能否 PostgreSQL+Redis。

## 五、12:30—13:15：数据真源审计

执行：
```
python 项目源码/verify_sources.py --manifest-only
python 项目源码/tools/anhui_web/validate_canonical_core.py
python 项目源码/wan-api/scripts/e2e_real_data.py
# 完整 source_data 存在时再加：
python 项目源码/verify_sources.py
```
验证 18 项：canonical schema / cycle 字段 / job_id 格式 / job_id 唯一性 / meta 守恒 / raw-active-excluded 守恒 / exclusion evidence 完整 / provenance 指纹 / canonical 与网站 jobs.json 对账 / 网站 manifest 哈希 / import_all_data 三周期导入 / MirrorState / Cycle / salary / review event / 第二次导入幂等 / 源字段清空不残留 / excluded 不进入用户口径。
任何数据差异必须先判定原因（真数据变化 / 生成器变化 / 版本变化 / fixture 变化 / 真实回归）——没有确定原因不得修改数据。

## 六、13:15—14:00：静态站构建和浏览器审计

```
python 项目源码/tools/anhui_web/clean_rebuild.py
python 项目源码/tools/anhui_web/verify_maintainable_site.py
node 项目源码/tests/test_wanyu_core.cjs
node 项目源码/tests/test_datastore_contract.cjs
node 项目源码/tests/test_major_city_index.cjs
node 项目源码/tests/test_user_store_contract.cjs
node 项目源码/tests/maintainable_browser_smoke.js        # playwright-core
node 项目源码/tests/major_city_browser_smoke.cjs
node 项目源码/tests/ui_upgrade_browser_smoke.cjs
```
重点：构建只读 canonical 不读旧 HTML；产物不是下次输入；manifest 路径全存在；gzip 配对；SW 版本一致；三周期按需加载；excluded 不进 jobs_lite/catalog/positions/major_city/ranking；详情无空白页；搜索/地图/待遇/审计/日历/收藏/对比/导出可用；localStorage 损坏不崩页；动态字段全 escapeHtml；SVG 文本安全；query/hash 不注入 DOM；CSV 防公式注入；移动端无横向溢出；深色模式对比度；失败请求有可理解错误与重试；API 未接入时不得假装云端同步成功。

## 七、14:00—15:00：API SQLite 门禁

`cd 项目源码/wan-api` 后执行：
```
python -m ruff check app tests --select E9,F63,F7,F82 --ignore E402
bash -n deploy.sh
bash -n scripts/backup_database.sh
bash -n scripts/restore_drill.sh
bash -n scripts/upgrade_drill.sh
ENV=test pytest tests/ -q
python scripts/e2e_real_data.py
DATABASE_URL=sqlite+aiosqlite:///./_ci_migrate.db alembic upgrade head
DATABASE_URL=sqlite+aiosqlite:///./_ci_migrate.db alembic check
DATABASE_URL=sqlite+aiosqlite:///./_ci_migrate.db alembic downgrade base
DATABASE_URL=sqlite+aiosqlite:///./_ci_migrate.db alembic upgrade head
DATABASE_URL=sqlite+aiosqlite:///./_ci_migrate.db alembic check
```
必须测试（存在性核对，缺哪项记 finding）：注册永远不是管理员 / 默认 SECRET_KEY 拒绝生产启动 / refresh 不走 query / refresh 单次轮换 / 重用撤销 family / logout 撤销 family / 未知邮箱 dummy bcrypt / 登录+register+refresh+logout 限流 / 搜索关键词转义 / page 超大拒绝 / snapshot Unicode 与超限 / saved position 不存在岗位拒绝 / excluded 岗位拒绝 / compare 第五个拒绝 / admin import 失败零写入 / 深嵌套 JSON 400 / 413 上限 / salary 0 保留 / review event 幂等 / stats import 后失效 / stats cache 容量上限 / 错误状态码稳定。

## 八、15:00—16:00：PostgreSQL、Redis、并发和安全

**本机无 Docker/psql/redis-cli → 本机真实后端 = BLOCKED_BY_ENVIRONMENT；证据通道 = CI postgres job（真 PG16+Redis7 service）：把改动推分支开 PR，等 `postgres` check 绿，`HTTPS_PROXY=http://127.0.0.1:7897 gh run view <id> --log` 摘录存 evidence/。**（PR 流程见附录 B-5）
若后续发现本机真实 PG/Redis 可用（如 WSL），先用连接探活再跑：
```
DATABASE_URL=postgresql+asyncpg://... REDIS_URL=redis://... RATE_LIMIT_BACKEND=redis ENV=test pytest tests/ -q
```
并发构造：两 refresh 同消费 / 两请求同加 compare slot / 同 review event 并发插入 / 两 limiter 实例共享 Redis / 多 worker 同 IP / Redis 暂不可达 / DB 连接暂时失败 / 导入期间读 stats / 导入失败期间读岗位。（CI 覆盖不到的并发场景，用本地 SQLite + asyncio.gather 近似，并在证据中注明近似性。）
安全矩阵：未登录访问 admin / 普通用户访问 admin / 改他人数据 / 被禁用用户访问 / 最后管理员降权与禁用 / CORS 非白名单 / refresh 泄漏 query / 恶意 keyword·JSON·文件名·job_id / 超大字段 / 非法 cycle / 非法与 unknown record_status / excluded 详情 / stale 收藏与对比。

## 九、16:00—17:00：部署和灾备审计

```
bash scripts/upgrade_drill.sh
pytest tests/test_ops_scripts.py -q
pytest tests/test_deploy_linkage.py -q
bash -n deploy.sh
```
审计 deploy.sh 完整顺序 PRECHECK→BUILD→SNAPSHOT→MIGRATE→IMPORT→SWITCH→START→SMOKE→COMMIT，重点：失败自动记录状态 / 失败自动恢复旧 current / 未健康新 release 不得成为永久 current / 迁移失败保护旧版本 / import 失败有恢复点 / smoke 失败切回旧 release / backup 非空且有 checksum / restore 明确建临时库且失败清理 / alembic revision 唯一 / Nginx root-alias 语义与 smoke 一致 / HTTP 301·HTTPS 200·root 302 契约 / 静态数据 cycles+salary+audit 存在性检查 / release 排除 tests·docs·*.db·audit probe / venv 全新 / lock 过 pip check / systemd 最小权限 / logrotate 存在 / prune 不删 current / backup retention 正确。
**没有真实 PostgreSQL 不得伪造 restore PASS——本机记 BLOCKED_BY_ENVIRONMENT，restore_drill.sh 的真实执行证据以 CI/历史 run 日志能核到的部分为限并注明来源。**

## 十、17:00—18:00：设计成熟架构

创建或更新 `docs/architecture/ADR-001-static-api-boundary.md`、`ADR-002-canonical-mirror-release.md`、`ADR-003-user-state-sync.md`。
默认选择：静态站=当前正式产品；wan-api=staging backend；不做半成品接入；未来动态化用 feature flag；岗位数据唯一真源=canonical，API 数据库只是 mirror。
若决定实现动态化，必须同时设计：API client / auth store / access+refresh token / logout / cloud positions·snapshots·compare / localStorage migration / conflict resolution / offline fallback / 401-403-429-503 UX / account deletion / data export / privacy policy / rate limit UI / retry strategy。

## 十一、18:00—19:00：实现 P0/P1 修复

优先修改对象：`wan-api/deploy.sh`、`scripts/{restore,upgrade}_drill.sh`、`app/services/import_service.py`、`app/models/`、`app/schemas/`、`app/api/v1/`、`app/utils/`、`migrations/versions/`、`tests/`、`.github/workflows/`、`tools/anhui_web/`、`网站/assets/`、`tools/anhui_web/templates/`。
要求：先写回归测试→确认当前版本失败→修根因→测试过→完整门禁→文档同步→版本号只在确定变更边界后 bump→不混不相关重构。
重点池（按 finding 实际支撑取舍，不硬凑）：deploy state machine / dry-run / rehearsal / rollback / release bundle / 三周期 hash 绑定 / review event 唯一约束 / salary-cycle 并发 upsert / jobs DB 约束 / stats cache 带 release-mirror 版本 / request id / structured logging / Redis fallback 告警 / import metrics / admin import response model / audit queue pagination / user positions pagination / snapshots pagination / CORS 严格 allowlist / 可控 optional auth 异常 / 窄化 advisory lock 异常 / refresh token 清理 / API 与前端 endpoint 对账 / CI EXCLUDED 测试归属。

## 十二、19:00—20:00：前端和用户体验质量

审计并修复：动态字段 escapeHtml / innerHTML 与 insertAdjacentHTML 数据源 / SVG 动态文本 / query-hash 注入 / localStorage 损坏与数据迁移 / 导入版本 / 导出脱敏 / CSV 注入 / 键盘导航 / aria / focus trap / 移动端 / 深色模式 / loading / empty / error / retry / SW 更新 / 三周期懒加载 / API 未接入时的本地模式说明。

## 十三、20:00—20:40：全量验证

```
python 项目源码/verify_sources.py --manifest-only
python 项目源码/tools/anhui_web/validate_canonical_core.py
python 项目源码/tools/anhui_web/verify_maintainable_site.py
cd 项目源码/wan-api
ENV=test pytest tests/ -q
python scripts/e2e_real_data.py
python -m ruff check app tests --select E9,F63,F7,F82 --ignore E402
bash -n deploy.sh
pip-audit -r requirements.lock.txt --strict
pip-audit -r requirements-dev.lock.txt --strict
```
有 PG/Redis 必须补跑真实后端门禁（CI 通道）；有 Chromium 必须补跑浏览器门禁。因环境缺失无法运行的：保存命令、环境、准确原因，不得写 PASS。

## 十四、20:40—21:00：生成报告和下一轮状态

生成：`baseline.json`、`findings.json`、`maturity-matrix.md`、`report.md`、`RESUME.md`、`state.json`、`verify/` 全部命令输出。
每条发现必须含：`{"id":"P1-xxx","severity":"P0|P1|P2","title":"...","status":"confirmed|fixed|rejected|blocked|waived","evidence":"file:line 或命令输出","impact":"...","root_cause":"...","fix":"...","tests":[...],"verification":[...],"remaining_risk":"..."}`

最终状态判定：
- **PRODUCTION_READY**：仅当真实 fresh-host、真实 PostgreSQL restore、COS 异机 restore、回滚、公网 smoke 全部有可复现证据。
- **STAGING_READY**：代码、构建、测试和 staging 流程可用，但生产证据尚未完成。
- **CODE_READY**：本地代码门禁通过，但环境门禁尚未完成。
- **BLOCKED_BY_EVIDENCE**：缺少真实环境证据且不能安全推断。
- **BLOCKED_BY_ENVIRONMENT**：工具或环境不可用。

没有真实证据时，最终回复必须明确写："本轮完成代码和测试层成熟化，但未宣称 Production Ready；剩余阻断项是……"。
**本窗口红线 14（不连生产）已预先封死全部生产证据获取通道 → 本窗口最终判级上界 = STAGING_READY，除非全部生产证据在本窗口前已存在且当前可复核（复核方式：引用可验证的 CI run / 服务器侧留痕文件，注明"未在本窗口重新取得"）。**

## 十五、最终回复格式

必须包含 14 项：1 本轮实际读取和审计的目录 / 2 当前 commit 和版本 / 3 当前数据基线 / 4 已发现的问题 / 5 已修复的问题 / 6 未修复的问题 / 7 被环境阻断的测试 / 8 所有验证命令和结果 / 9 变更文件 / 10 生成的 evidence 文件 / 11 当前成熟度等级 / 12 下一轮只做什么 / 13 是否允许部署 / 14 明确声明有没有修改生产环境。
禁用词（除非有真实命令输出/日志/可复现证据）："应该没问题"、"理论上可以"、"全部完成"、"Production Ready"、"灾备完成"、"线上安全"。

---
---

# 附录 A：接管预检事实（2026-09-09 00:39—00:50 实测，可直接引用但关键门禁仍须重跑）

| 项 | 实测值 |
|---|---|
| 当前时刻 | 2026-09-09 00:39 +0800（窗口 12:00 前的预检） |
| 仓库根 | **`E:\zcode\择岗`**（不是 项目源码/！`git rev-parse --show-toplevel` 实测） |
| 分支/HEAD | main = `bef9fe9`（v17.9.19，PR#20 合并点），与 origin/main 同步（代理 fetch 实测），工作树仅 2 个 untracked docs 目录 |
| GitHub | `2421873411a-rgb/wanyu-zegang`（公开仓，branch protection：test+canonical+postgres required，enforce_admins） |
| 网站版本源 | `项目源码/release.json` = v17.9.0（asset 17.9.0，SW wanyu-shell-v50）——与 API 版本分离 ✓ |
| API 版本源 | `项目源码/wan-api/release.json` = v17.9.19 |
| 数据基线 | `docs/current-status.md` 实测：2024=10017/10017/0，2025=10150/10150/0，2026=8511/8401/110——与第一节口径一致 ✓（12:00 仍须重核） |
| Python | 3.11.9（wan-api 全套测试本机可跑） |
| Node | v24.18.1 |
| pip-audit | 2.7.3 ✓ |
| Docker | ✗ 无 → 本机无容器化 PG/Redis |
| psql / redis-cli | ✗ 无 → 八、九节真实后端门禁本机 = BLOCKED_BY_ENVIRONMENT，证据走 CI postgres job |
| playwright | python 包可 import；`项目源码/tests/` 浏览器 smoke 用 **node playwright-core**；`%LOCALAPPDATA%\ms-playwright` 已有 chromium-1234/1243 + headless_shell → 浏览器门禁**预期可跑**（跑不了才准标 BLOCKED） |
| workflows | 仓库根 `.github/workflows/`：`wan-api-ci.yml` + `canonical-ci.yml`（规范中"项目源码/.github/workflows"按此实际路径理解） |
| 关键脚本存在性 | `verify_sources.py` ✓、`tools/anhui_web/{validate_canonical_core,clean_rebuild,verify_maintainable_site}.py` ✓、`wan-api/scripts/{e2e_real_data.py,backup_database.sh,restore_drill.sh,upgrade_drill.sh}` ✓、node 测试 8 个 ✓、`网站/index.html`+`data/site-manifest.json` ✓、`docs/current-status.md` ✓、`requirements{,-dev}.{txt,lock.txt}` ✓ |
| node 测试清单 | test_wanyu_core.cjs / test_datastore_contract.cjs / test_major_city_index.cjs / test_user_store_contract.cjs / maintainable_browser_smoke.js / major_city_browser_smoke.cjs / ui_upgrade_browser_smoke.cjs / browser_smoke_v12.js |

# 附录 B：执行修正与纪律（与规范冲突时以规范红线为准，这里只补操作层）

1. **网络代理（Clash）**：`git fetch/push` 用 `git -c http.proxy=http://127.0.0.1:7897 fetch origin`；`gh` 用 `HTTPS_PROXY=http://127.0.0.1:7897 gh api …`（REST 实测可用）。已知坑：`gh pr list`（GraphQL）经代理 EOF——PR 状态改走 REST（`gh api repos/…/pulls`、`gh pr checks` 若失败改 `gh api repos/…/commits/<sha>/check-runs`）。匿名 curl 会撞 rate limit——**API 证据一律走认证 gh**。
2. **本机 PG/Redis 缺失的补偿通道**：改动推分支开 PR → CI 的 `postgres` job 是真 PG16+Redis7（含 RATE_LIMIT_BACKEND=redis）→ run 结论+关键日志摘录存 `evidence/ci-pg-redis/`。CI 覆盖不到的并发场景用 SQLite+asyncio.gather 近似并在证据里注明近似性（规范第八节已授权）。
3. **判级上界**：红线 14 封死生产取证 → 本窗口目标现实定为 **STAGING_READY**（若 8/13 节有 BLOCKED 则相应降级）。不要试图连生产"补证据"。
4. **PR/合并纪律**：main 受保护不可直推；分支从当刻 origin/main 拉（命名 `maturity/<阶段>-<主题>`）；一次 PR 只装一件事；等 test+canonical+postgres 三 check 全 success 才 merge；**每个修复先有失败测试**（规范 §2.20）。等待 CI 期间不空转——做下一阶段只读审计。
5. **时间纪律强化**（规范时钟块是目标，不是硬墙；越线规则）：
   - 每阶段结束立即更新 `state.json` + `verify/<阶段>.md` 落盘命令输出——会话中断后凭 state.json 续跑，不重做已完成阶段。
   - 任一阶段发现 P0 → 立即插队处理（先失败测试→修复），原阶段顺延。
   - 某阶段超时 50% → 砍非必需项进入下一阶段，砍掉什么写进 report。
   - 19:00 前必须完成全量验证的至少一轮（即使修复未完），20:00 后不再新开修复，20:40 硬进入报告。
   - 21:00 硬停：宁可报告简短，不可无报告。
6. **Windows Git Bash 陷阱**：转义敏感代码只走 Read+Edit 不走 heredoc；`git show ref:path` 加 `MSYS_NO_PATHCONV=1`；`| tail` 会吞退出码——判门直取 `$?` 或写日志文件；http.server 的 CWD 别放在会被 rename 的目录里。
7. **版本号**：网站（v17.9.0）与 API（v17.9.19）两源独立；本窗口若有 API 代码变更合入 main → bump 到 v17.9.20（patch）；网站产物若变更 → 站长规范另有流水线纪律（release.py 先测试后管线），不要在本窗口擅自重跑整站发布——产物重建验证用 `clean_rebuild.py` 输出到 staging 对比，不覆盖 `网站/` 正式产物（§2.22 同理）。`docs/current-status.md` 是生成器产物勿手改。
8. **memory 文件**：`C:\Users\24218\.zcode\cli\memories\projects\project-43b20c5c577d5795\memory\self-iterate-lessons-wanyu.md` 有 24 条历史教训（heredoc 腐败/声称修复≠落盘/CI 假绿三查/PG 假 SQLite/多 service 端口合并/aioredis 循环绑定/sites-enabled 副本/systemd PrivateTmp 等）——开工通读，避免重蹈。

**开工第一句：`date` + 更新 state.json(status=RUNNING, started_at) + 通读 memory 教训文件。然后按第四节走。**
