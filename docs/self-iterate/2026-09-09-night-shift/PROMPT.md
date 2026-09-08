# 皖域择岗 夜班全自动自迭代任务书（2026-09-09 00:00 → 09:00）

> 本文件是夜班代理的**完整任务书**。把它作为新会话的第一条消息即启动夜班。
> 全自动：**全程禁止向用户提问**（不使用 AskUserQuestion）。所有分歧按本文件规则自行裁决。
> 09:00 前必须产出晨报并停止。宁可晨报简短，不可无晨报。

---

## 0. 使命

把皖域择岗从「已收敛的 v17.9.19」推进到「成熟」：

1. **审计驱动修复**：多轮对抗审计 → 证伪 → 修复 → PR 合并，直到收敛（连续 2 轮 P0=P1=0）。
2. **特性落地**：可观测性（Observability）+ 安全生命周期（Security Lifecycle）精选项（§5 工作池）。
3. **S8 全面验证**：全量测试 / 依赖漏洞 / 脚本语法 / 备份恢复演练 / 压测 / 安全回归。
4. **生产部署**：把 wan.kaogong.art 从 v17.9.18 升到当晚终版（含已在 main 上但未部署的 v17.9.19）。
5. **收尾**：晨报、桌面交接包重建、memory 更新。

主题版本号：**今晚终态目标 v17.10.0**（可观测性套件整体落地即升 minor）；若 04:30 特性冻结前 W1/W2 未整体落地，则终态为最高 patch 版（v17.9.20+）并如实报告。

---

## 1. 基线事实（2026-09-08 深夜逐一核对过，直接可信）

| 项 | 值 |
|---|---|
| 本机工作区 | `E:\zcode\择岗\`（Windows，Git Bash） |
| 后端仓库 | `E:\zcode\择岗\项目源码\wan-api`（唯一 git 仓库） |
| main | `bef9fe9` = v17.9.19（PR#20 已合并，本地与 origin 同步，工作树干净） |
| 远程仓库 | `github.com/2421873411a-rgb/wanyu-zegang`（**公开仓**） |
| branch protection | required = `test` + `canonical` + `postgres`（绑 GitHub Actions），enforce_admins=true，main 不可直推 |
| 生产 | https://wan.kaogong.art 运行 **v17.9.18**（落后 main 一个版本，今晚补齐） |
| 服务器 | `ubuntu@175.27.132.225`（Ubuntu 24.04，多站点共用） |
| SSH 私钥 | `E:\zcode\择岗\_密钥_勿入git\wanyu_deploy_ed25519`（**用这把**；`wanyu111_fixed.pem` 已从服务器 authorized_keys 移除，不可用） |
| git 推送 | 走 Clash：`git -c http.proxy=http://127.0.0.1:7897 push …`（gh 失败时加 `https_proxy=http://127.0.0.1:7897`） |
| 版本单一真源 | `项目源码/wan-api/release.json`（wanyu-api-release/v1；APP_VERSION 由 config 启动读取 + deploy.sh 注入 + smoke 断言，**绝不手填**） |
| 本地测试基线 | pytest（SQLite）v17.9.18 时为 78 passed + 5 skipped 零警告；PR#20 新增 test_ops_scripts.py 后会更多——**以开工实测为准并记录为新基线** |
| CI 三 required | `test`（SQLite 全套）、`canonical`（数据契约+node cjs）、`postgres`（PG16+Redis7 真跑，83+） |
| CHANGELOG | `项目源码/deliverables/CHANGELOG.md` |
| 今夜产物目录 | `E:\zcode\择岗\docs\self-iterate\2026-09-09-night-shift\`（evidence/ verify/ 子目录，本文件已在内） |
| 历史教训 | `C:\Users\24218\.zcode\cli\memories\projects\project-43b20c5c577d5795\memory\self-iterate-lessons-wanyu.md`（24 条）——**开工先通读一遍** |

---

## 2. 红线（任何时刻不得违反，违者立即停止该动作并记录）

1. **不改岗位原文数据**；未知字段不补 0。
2. **`_密钥_勿入git/` 绝不进 git、绝不进交接包 tar 之外的任何上传物**。仓库公开——密钥入 git 即泄漏，若发生立即换钥并在晨报置顶。
3. main 受保护：**只能走 PR**；不 force-push main；不改 branch protection 设置；不解散 required check。
4. **红色 CI 不合并、不部署**。CI 真绿三查：读 run 的 conclusion（`gh run view <id> --json conclusion`）而非徽章；确认无关键 skip；确认无同名 status 顶替。
5. 生产部署**必须**走 deploy.sh（自带迁移前 pg_dump + .alembic-before.txt sidecar + smoke 版本断言）；部署失败或新版本异常**立即回滚**，回滚顺序铁律：**先用新 release 把库降到旧 revision，再切旧 release**（顺序反了会 "Can't locate revision"）。
6. 无人值守夜班**只允许 expand 型迁移**（加列/加索引/回填），禁止 drop/rename/收窄（contract 型一律推迟到白天有人在场）。
7. **每个修复 = 落盘字节变更 + 一条正向门禁测试**。不接受"提交信息声称已修"（v17.9.13 实测教训）。
8. Windows Git Bash：转义敏感代码（正则/escape/续行符）**只用 Read+Edit 工具改，绝不走 heredoc**；改完 `od -c`/测试双验；`git show ref:path` 需 `MSYS_NO_PATHCONV=1`。
9. 生产服务器上只做本任务书授权的动作（部署/验证/演练/回滚），不做额外探险、不装计划外软件、不动其他站点（zcode.kaogong.art 的 502 是既有问题，今晚不碰）。
10. **时间铁律**：08:30 无论进行到哪，强制进入收尾；09:00 硬停。

---

## 3. Phase 0 — 开机自检（00:00–00:30，超时砍非必需项）

按序执行，每步结果写入 `evidence/phase0-baseline.md`：

1. `date` 记录实际开工时刻。创建 `state.json`（格式见 §9）。
2. `git -C 项目源码/wan-api fetch origin && git status -sb`：断言 main==origin/main 且干净。若落后→先 `git pull --ff-only`；若分叉→记录并以 origin/main 为准。
3. `gh run list --repo 2421873411a-rgb/wanyu-zegang --branch main --limit 3`：三个 required check 最新结论必须全 success；有红→Phase 1 第 0 优先级是修 CI。
4. `gh pr list`：有外部 PR 一律不自动合并，只在审计中作为线索参考。
5. 本地全量测试：`cd 项目源码/wan-api && python -m pytest -q`，记录通过数/跳过数/警告数为**今夜基线**。基线红→先修到绿。
6. 生产探活：`curl -s https://wan.kaogong.art/health`（期待 `{ok, v17.9.18, db:ok}`）+ `curl -s "https://wan.kaogong.art/api/v1/jobs/search?page_size=1"` 记 total。
7. SSH 连通：`ssh -i /e/zcode/择岗/_密钥_勿入git/wanyu_deploy_ed25519 -o ConnectTimeout=10 ubuntu@175.27.132.225 'echo ok; readlink /opt/wanyu/current; df -h /opt | tail -1'`。
8. 通读 memory 三文件（§1 表末路径 + night-shift-loop.md + wan-project-handoff.md）。
9. 写 `RESUME.md`（初版）+ `state.json`。

**降级决策**（自动执行，不问人）：SSH 不通→今晚不部署，Phase 3 改为"部署预演到 --build-only 为止"并晨报置顶；CI 红→先修红再开审计轮；测试基线红→先修基线。

---

## 4. Phase 1 — 主迭代循环（00:30–06:30，每轮 ≤70min，**至少 3 轮，最多 5 轮**）

### 每轮固定协议（Round N）

1. **派审计**（并行 2 个子代理，同一 main HEAD，各自独立、互不可见对方结论）：
   - **审计员 A「安全与注入面」**：`app/api/v1/*`、`app/schemas/*`、`app/utils/security.py`、`app/utils/rate_limit.py`、CORS/安全头/SECRET_KEY 门禁/权限矩阵（普通用户 vs admin 端点全表核对）。
   - **审计员 B「正确性与运维链」**：`app/services/*`、`app/models/*` + alembic 迁移一致性、`deploy.sh`、`scripts/*.sh`、`.github/workflows/*`、tests 假绿（fixture 尊重 DATABASE_URL？skip 是否掩盖？）、`tests/test_deploy_linkage.py` 是否仍锁全部署面。
   - **每轮轮换第三视角**（R1 可观测性缺口 / R2 依赖供应链与 lock 健康 / R3 性能 N+1 与缓存一致性 / R4 数据一致性与快照链路 / R5 自由复审）。
   - 审计提示词必须要求：每条 finding 给 `file:line` 证据 + 可复现思路 + 严重级（P0=生产事故/数据损坏/安全洞；P1=功能坏/门禁失效/部署链断；P2=质量/可维护性）+ 建议的门禁测试写法。**明确要求审计员先证伪自己**（排除检查器误报类：`.get()+or` 陷阱、假差异）。
2. **证伪**：逐条亲手复现——写失败测试或最小复现命令，跑通才算数。复现不出→降级 P2 存档或标 `unverified` 丢弃。审计原文全存 `evidence/roundN-audits.md`。
3. **triage**：写 `roundN-triage-and-plan.md`：P0 立刻修；P1 本轮修；P2 进清单择优；won't-fix 必须写理由。
4. **修复**（TDD）：先写**失败的**门禁测试 → 修 → 测试转绿 → 跑相关测试子集 → 最后全量。转义敏感改动走 Read+Edit（红线 8）。
5. **提交合并**：分支 `night/roundN-<topic>` **从当刻 origin/main 拉**（绝不用陈旧 base）；PR；`gh pr checks` 等 test+canonical+postgres 全 success；merge（squash 优先）；删分支。**一次 PR 只装一轮的内容**，禁止跨轮积压。
6. **版本**：本轮有代码变更 → bump `release.json`（patch 递进 v17.9.20, v17.9.21…；可观测性套件整体落地那次定 v17.10.0）+ CHANGELOG 条目 + commit（可随修复 PR 同 PR 提交）。
7. **落盘**：`state.json` 更新；`verify/roundN-gates.md` 记录全量测试输出与 CI 链接。

### 收敛判定

**连续 2 轮 P0=P1=0 → 收敛**，进 Phase 2。且收敛宣称时间不得早于 **03:30**（防浅审计假收敛；轮次下限 3 就是为此）。

### 硬止损

- 04:30 **特性冻结**：此后不再新开工作池项，只做审计修复。
- 05:30 未收敛：P2 全部封存，只修 P0/P1。
- 06:30 Phase 1 **强制结束**：未收敛也结束，如实报告剩余 P0/P1。
- 任何时刻若发现 P0 修复本身引发新 P0（回归），回滚该修复 PR（`git revert`），记入晨报。

---

## 5. 候选工作池（P0/P1 审计发现永远优先；本池只在无 P0/P1 待修时动用）

| # | 项 | 内容 | 验收门禁 |
|---|---|---|---|
| W1 | **可观测性** | ① request-id 中间件（生成/透传 `X-Request-ID`，访问日志 JSON 结构化含 method/path/status/duration/request-id）；② `/metrics` Prometheus 文本格式（请求数/延迟直方图/错误分类计数，**必须**限内网或 token 保护，不得公开泄漏业务计数细节）；③ 慢查询日志（>200ms 记录语句与耗时）；④ RUNBOOK 增加「日志怎么读/告警看什么」一节 | 门禁测试：request-id 回显、/metrics 未授权 401、日志 JSON 可解析；deploy_linkage 测试补 /metrics 路由锁 |
| W2 | **安全生命周期** | ① `.github/dependabot.yml`（pip + github-actions，weekly）；② CI 增加 weekly schedule 的 pip-audit job（对 requirements.lock，**不吞退出码**，失败即红）；③ SBOM：`pip-audit -r requirements.lock.txt --format cyclonedx-json` 产物入 Release assets；④ RUNBOOK 增加「密钥轮换 runbook」（SSH 钥/SECRET_KEY/管理员密码各一节，只写步骤不写值） | CI 实际出现 schedule 触发记录；本地跑 pip-audit 0 高危；SBOM 生成成功 |
| W3 | 备份异地化文档 | COS 上传代码已存在——RUNBOOK 补齐「从零配置 COS 异地副本 + 异机恢复演练」手册（凭据只留服务器） | 文档评审：步骤可照抄执行 |
| W4 | CJK 短词搜索优化 | 有余力才做；先建搜索质量用例集（≥20 条真实查询的期望命中），再调 | 质量用例不回退；性能 p95 不回退 |

**明确不做**（做了算违规）：v18.0 HA、contract 型 DB 迁移、前端站点大改、任何需要腾讯云控制台人工操作的事（skey-* 解绑、COS 密钥申请——只能晨报列为人工待办）、外部 PR 的自动合并。

---

## 6. Phase 2 — S8 全面验证（收敛后立即，最晚 07:00 开始）

全部结果写 `verify/s8-report.md`，任一 FAIL→时间允许则回 Phase 1 修，否则记录并影响部署判据：

1. 本地全量 pytest（含新增测试）零失败零新增警告；对比 Phase 0 基线只增不减。
2. `pip-audit -r requirements.lock.txt`：0 已知高危。
3. `bash -n deploy.sh scripts/*.sh` 全部语法过。
4. `bash scripts/upgrade_drill.sh`（四不变量：幽灵文件/依赖漂移/幂等重建/原子切换回滚）PASS。
5. 服务器备份链验证：SSH 上跑 `bash /opt/wanyu/current/app/scripts/restore_drill.sh` PASS（先 createdb 后 pg_restore 是脚本内置）。
6. 压测：对 `/health` 与 `/api/v1/jobs/search?q=…`（本地起服务或服务器 127.0.0.1 打）各 1000 请求记录 p95 与错误数；与 Phase 0 基线对比不回退 >20%。
7. 安全回归（多数由既有测试套保证，确认其在跑）：未认证写端点全 401/403、限流 429 触发、SECRET_KEY 生产门禁矩阵、refresh 轮换重用检测。

---

## 7. Phase 3 — 生产部署（07:30–08:15，**判据制**）

### 部署判据（全部满足才动手，任一不满足→明确弃权并晨报说明）

- [ ] 部署目标 commit = main HEAD 且其上三 required check 全 success
- [ ] S8 全 PASS（或有已记录理由的豁免）
- [ ] 时刻 ∈ [07:30, 08:00]（保证 15min 验证 + 15min 收尾；08:00 后一律弃权）
- [ ] SSH 通；`df -h /opt` 余量 >2GB；`readlink /opt/wanyu/current` 确认当前 release
- [ ] 待部署版本相对 v17.9.19 的 alembic 迁移**全部 expand 型**（逐个 diff revisions 目录确认，红线 6）

### 步骤（以 deploy.sh 与 RUNBOOK 为准，先查上轮部署实录 `verify/round-9-production-chain-repair.md` 复用成功命令序列）

1. 代码上服务器：`git -C 项目源码/wan-api archive HEAD | ssh -i <key> ubuntu@175.27.132.225 'mkdir -p /tmp/wanyu-stage && tar -x -C /tmp/wanyu-stage'`（或复用上轮上传方式）。
2. 服务器执行部署（deploy.sh 自建 `/opt/wanyu/releases/<ver>-<sha>/` 新目录+新 venv，原子切链，内置迁移前 pg_dump 与 smoke 版本断言）：
   `ssh … 'cd /tmp/wanyu-stage && sudo -E bash -c "source ./deploy.sh"'`（sudo/env 细节以 deploy.sh 顶部 usage 为准；上轮怎么跑成功的就怎么跑）。
3. smoke：deploy.sh 自断言 `/health` 版本==部署版本；另手工核对 `curl -s https://wan.kaogong.art/health` → `{ok, <新版本>, db:ok}`。
4. 部署后验证清单（全过才算成）：`/health` 版本正确；`/api/v1/jobs/search?page_size=1` total≈28568；注册→登录→refresh→登出全链路（用一次性测试邮箱）；admin 凭据登录（`/opt/wanyu/credentials/admin.txt`）；静态站 200 + http→https 301；`journalctl -u wanyu-api -n 50 --no-pager` 无 ERROR/Traceback；`systemctl status wanyu-api` active。
5. **观察 10 分钟**：期间每 3 分钟再打一次 /health 与一条搜索，日志尾巴无异常。
6. **失败即回滚**（不等不猜）：按 RUNBOOK「回滚」节——先用新 release `alembic downgrade <sidecar 里的 old_rev>`，再 `ln -sfn` 旧 release + `mv -T` 原子切 + sed 回写 `/etc/wanyu/wanyu.env` 的 APP_VERSION + restart + 本地 /health 验证。回滚也算合法结局，如实晨报。
7. 成功后：推 tag、`gh release create <ver> --notes <CHANGELOG 摘录>`（挂 SBOM 若 W2 落地）。

---

## 8. Phase 4 — 收尾（08:15–08:30 开始者按实际时刻顺延，08:30 强制开始，09:00 硬停）

1. **晨报** `report.md`（格式见 §10），并同步为最终聊天消息。
2. `RESUME.md`：完结写 `done=true`；未完结写清续作点。
3. `state.json` 终态。
4. **桌面交接包重建**（09-08 的交接包已不在桌面，本项为**必做**）：
   - 目标：`C:\Users\24218\Desktop\皖域择岗_交接包_20260909\` + 同名 `.tar.gz` + `.sha256`
   - 内容：`README.md`（终版概览+链接+密钥位置+站长人工待办）、`_密钥_勿入git/` 整目录复制（**含 wanyu_deploy_ed25519**，并修正其中过期的 README——它还在写已废弃的 wanyu111 指引）、`项目源码/`（排除 `.venv`、`__pycache__`、`node_modules`、`*.db`、临时产物）、`git bundle`（`git -C 项目源码/wan-api bundle create wanyu-zegang.bundle --all`）
   - 打包：Git Bash `tar -czf`；`sha256sum` 落 `.sha256` 文件；记录包大小
5. **memory 更新**：改写 `night-shift-loop.md` 与 `wan-project-handoff.md` 为今夜终态（版本、main sha、部署状态、新增教训，若有新教训也并入 `self-iterate-lessons-wanyu.md`）。
6. 最终消息 = 晨报摘要 + 关键链接（repo/releases/actions/PR/晨报文件路径）。

---

## 9. 上下文存续协议（会话可能中途断，靠落盘续命）

每轮/每阶段结束必须写 `state.json`：

```json
{
  "phase": "P1-round-3-fix",
  "started_at": "…", "updated_at": "…",
  "main_head": "<sha>", "release": "v17.9.21",
  "merged_prs": [20, 21], "open_pr": 22,
  "open_p0": [], "open_p1": ["…id…"],
  "deploy": "pending",
  "next_action": "…一句话…"
}
```

若会话重启：先读本文件 + `state.json` + `RESUME.md`，从 `next_action` 继续；已合并轮次不重做；时间按绝对钟（09:00 硬停不变）。

---

## 10. 时间纪律与晨报格式

### 时钟强制点（每小时查一次 `date`，越线即执行对应动作，不商量）

| 时刻 | 动作 |
|---|---|
| 00:30 | Phase 0 未完→砍非必需项强制进 Phase 1 |
| 03:30 | 此前禁止宣称收敛 |
| 04:30 | 特性冻结 |
| 05:30 | 只修 P0/P1 |
| 06:30 | Phase 1 强制结束 |
| 07:00 | S8 必须已开始 |
| 07:30–08:00 | 部署窗口（窗外弃权） |
| 08:30 | 收尾强制开始 |
| 09:00 | 硬停，晨报必须已存在 |

### 晨报格式（report.md 与最终消息一致）

```
# 皖域择岗 夜班晨报 2026-09-09
- 结论一句话：<成/部分成/中止> + 终版 + 生产是否已上线
- 版本跃迁：v17.9.19 → <终版>；main=<sha>；tags=[…]
- 审计轮次：N 轮（子代理 ×2N 个）；P0×a P1×b P2×c；关闭明细表（finding→修法→门禁测试→PR）
- 特性落地：W1/W2/W3/W4 各 自查/落地/未动 + 证据
- S8：7 项逐项 PASS/FAIL/豁免
- 部署：<时刻> v<版本> 上线；smoke 与验证清单结果；（或）弃权/回滚原因
- 残余风险与人工待办：腾讯云 skey-* 解绑、COS 密钥与异机恢复演练、zcode.kaogong.art 502、（今夜新增）
- 产物清单：晨报/RESUME/state/evidence×N/verify×N/交接包 路径
- 链接：repo / releases / actions / PR×N
```

---

## 11. 环境速查卡

```bash
# 时间
date
# git（在 E:\zcode\择岗\项目源码\wan-api）
git -c http.proxy=http://127.0.0.1:7897 push origin <ref>
git -c http.proxy=http://127.0.0.1:7897 pull --ff-only
# gh（网络失败加 https_proxy=http://127.0.0.1:7897）
gh run list --repo 2421873411a-rgb/wanyu-zegang --branch main --limit 5
gh pr checks <num> --repo 2421873411a-rgb/wanyu-zegang --watch
# 本地测试（Python 3.11 全套可跑）
cd /e/zcode/择岗/项目源码/wan-api && python -m pytest -q
# SSH（Git Bash 路径；先 chmod 600 该钥）
ssh -i /e/zcode/择岗/_密钥_勿入git/wanyu_deploy_ed25519 ubuntu@175.27.132.225
# 生产探活
curl -s https://wan.kaogong.art/health
curl -s "https://wan.kaogong.art/api/v1/jobs/search?page_size=1"
# Windows 陷阱
MSYS_NO_PATHCONV=1 git show <ref>:<path>   # git show ref:path 防路径改写
```

生产布局：`/opt/wanyu/releases/<ver>-<sha>/{app,venv}`（root:root 只读）+ `/opt/wanyu/current` 软链；secret `/etc/wanyu/wanyu.env`（640 root:www-data）；日志 `/var/log/wanyu`；备份 `/opt/wanyu/backup`（timer daily 03:00）；管理员凭据 `/opt/wanyu/credentials/admin.txt`（600）。**该机 nginx sites-enabled 是普通文件副本非软链**；**systemd unit 已含 PrivateTmp=true 勿动**。

---

## 12. 历史教训 TOP（完整 24 条在 memory，开工通读；这里是高频复发项）

1. heredoc 会写坏转义敏感代码（SOH/退格/续行符三发实锤）→ 只用 Read+Edit，配**正向**门禁。
2. "声称修复"必须字节级验证（`git log -S` / `od -c`），commit message 不算数。
3. CI 假绿三查：读 conclusion 非徽章、无掩盖性 skip、无同名 status 顶替。
4. 测试 fixture 必须尊重 `DATABASE_URL`（PG 假 SQLite 教训）；PG 共享库需 per-test drop/create。
5. 迁移漂移检测必须真实两库列级对比 + exit 1，print WARNING=假门禁。
6. Actions 多 service 容器要**逐个显式 ports:**。
7. aioredis 连接绑定事件循环——fixture 清理用同步短连接。
8. deploy.sh 改动后必跑 `bash -n`（CI 已有该门禁，本地先跑）。
9. 版本只认 `wan-api/release.json` 单一真源；APP_VERSION 不手填。
10. 验收 FAIL 先证伪检查器本身（`.get()+or ≠ ??` 假差异教训）。
11. 分支任何 reset/--hard 前确认 HEAD 无未推提交。
12. 部署面 import 已被 `tests/test_deploy_linkage.py` 锁定——动 deploy.sh/路由/workers 必跑它。

---

**开工第一句：`date` + 读 memory 三个文件 + 建目录落 state.json。然后按 Phase 0 走。**
