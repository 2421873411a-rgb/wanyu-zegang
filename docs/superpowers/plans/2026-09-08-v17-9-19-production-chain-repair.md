# v17.9.19 Production Chain Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 v17.9.18 部署、fresh-host smoke、数据库备份/恢复和升级演练中的确定性断链，并撤回没有证据支撑的 Production Hardening PASS。

**Architecture:** `deploy.sh` 只保留一个版本解析入口和一个 release 构建实现；可执行脚本用 `main`/dispatch 边界支持无副作用加载，以便 pytest 驱动真实 shell 行为。数据库备份独立为可直接执行和测试的脚本，默认仍落本机恢复点，并在显式配置 COS 后同步 dump 与 checksum；恢复演练使用临时库、退出清理和 immutable release 的真实 venv 路径。

**Tech Stack:** Bash 5、pytest 9、Python 3.12、PostgreSQL 16、systemd、Nginx、腾讯云 `coscli`。

**Execution status (2026-09-08):** Tasks 1–7 have been implemented and locally
verified on `codex/fix-v17.9.19-production-chain`; fresh-host、生产部署、COS
异机下载与恢复仍按证据边界保持未运行。

## Global Constraints

- 当前修复基线必须是 `main` HEAD `7c2d011917482ae7cf5d1c7285094b74d6bf7c23`。
- 不改 canonical 数据、API 业务语义或用户现有未跟踪文件 `交接说明_README.md`。
- 本地测试不得伪装 fresh-host、生产部署或异机恢复已经完成。
- 所有生产路径默认保持 `/opt/wanyu`、`/etc/wanyu`、`/var/log/wanyu`，测试只通过显式环境变量重定向临时目录。
- API 版本单一真源仍为 `项目源码/wan-api/release.json`，本轮目标版本为 `v17.9.19`。
- 每个行为修复先运行新增测试并确认按预期失败，再写最小实现使其通过。

---

### Task 1: 可测试且无副作用的 deploy.sh 入口

**Files:**
- Modify: `项目源码/wan-api/deploy.sh`
- Create: `项目源码/wan-api/tests/test_ops_scripts.py`

**Interfaces:**
- Consumes: Bash 的 `BASH_SOURCE[0]` 与 `$0`。
- Produces: `dispatch()`；source `deploy.sh` 时不执行部署，直接运行时仍进入 CLI 分发。

- [ ] **Step 1: Write the failing test**

```python
def test_deploy_script_can_be_sourced_without_running_main(bash, wan_api):
    result = bash(f'source "{wan_api}/deploy.sh"; printf sourced')
    assert result.returncode == 0
    assert result.stdout.endswith("sourced")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `ENV=test pytest tests/test_ops_scripts.py::test_deploy_script_can_be_sourced_without_running_main -q`

Expected: FAIL because current footer executes `main "$@"` while sourced.

- [ ] **Step 3: Write minimal implementation**

```bash
dispatch() {
    if [ "${1:-}" = "--build-only" ]; then
        build_only_main
    else
        main "$@"
    fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    dispatch "$@"
fi
```

- [ ] **Step 4: Run test to verify it passes**

Run: `ENV=test pytest tests/test_ops_scripts.py::test_deploy_script_can_be_sourced_without_running_main -q`

Expected: PASS.

---

### Task 2: 版本先解析且 build-only 复用唯一构建实现

**Files:**
- Modify: `项目源码/wan-api/deploy.sh`
- Modify: `项目源码/wan-api/tests/test_ops_scripts.py`
- Modify: `项目源码/wan-api/scripts/upgrade_drill.sh`

**Interfaces:**
- Produces: `load_release_metadata()` 设置非空 `APP_VERSION`；`build_release()` 是生产和 `--build-only` 的唯一实现；`WANYU_RELEASE_SUFFIX` 只改变演练目录后缀。

- [ ] **Step 1: Write failing version-order and build-delegation tests**

```python
def test_main_loads_release_before_secret_setup(...):
    # 慢/外部步骤替换成记录器，真实 load_release_metadata 读取临时 release.json。
    # setup_secret_env 观察到的值必须是 v17.9.19。

def test_build_only_delegates_to_build_release(...):
    # 覆盖 build_release 为记录器；build_only_main 必须恰调用一次。
```

- [ ] **Step 2: Run both tests and verify RED**

Run: `ENV=test pytest tests/test_ops_scripts.py -k "loads_release or delegates" -q`

Expected: FAIL because `load_release_metadata`/`build_only_main` 不存在且旧 main 顺序错误。

- [ ] **Step 3: Extract the single implementation**

```bash
load_release_metadata() {
    [ -f "$RELEASE_JSON" ] || { log_error "版本真源缺失：${RELEASE_JSON}"; return 1; }
    APP_VERSION="$(python3 -c "import json; print(json.load(open('$RELEASE_JSON'))['release'])")"
    [[ "$APP_VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
}

main() {
    check_root
    load_release_metadata
    check_prerequisites
    # ... setup_database
    setup_secret_env
    build_release
}

build_only_main() {
    check_root
    load_release_metadata
    WANYU_RELEASE_SUFFIX="-drill"
    build_release
}
```

`build_release()` 内不再解析版本；它统一使用与生产完全相同的 tar exclude、权限和 fresh venv 流程。

- [ ] **Step 4: Add and run a payload behavior test**

测试用真实 `build_release()` 复制临时载荷，只替换 root/venv 外部边界；断言 `tests/`、`docs/`、`*.db`、`_audit_probe*` 均未进入 app，而普通模块存在。

Run: `ENV=test pytest tests/test_ops_scripts.py -k "build_release" -q`

Expected: RED before the extraction, then PASS after both CLI paths share `build_release()`.

---

### Task 3: fresh-host 根路径的 redirect-aware smoke

**Files:**
- Modify: `项目源码/wan-api/deploy.sh`
- Modify: `项目源码/wan-api/tests/test_ops_scripts.py`

**Interfaces:**
- Produces: `smoke_public_root()` follows HTTPS redirects and requires the final response to be 200; HTTP still must redirect to HTTPS.

- [ ] **Step 1: Write the failing behavior test**

```python
def test_public_root_smoke_accepts_template_redirect_and_requires_final_200(...):
    # fake curl returns 302 without -L and 200 with -L.
    # Invoke the real smoke_public_root function and assert exit 0.
```

- [ ] **Step 2: Verify RED**

Run: `ENV=test pytest tests/test_ops_scripts.py::test_public_root_smoke_accepts_template_redirect_and_requires_final_200 -q`

Expected: FAIL because the helper is absent and the old check rejects 302.

- [ ] **Step 3: Implement the redirect-aware check**

```bash
code="$(curl -sL -o /dev/null -w '%{http_code}' https://wan.kaogong.art/)"
[ "$code" = "200" ] || { log_error "静态站最终返回 ${code}（期望 200）"; return 1; }
```

- [ ] **Step 4: Verify GREEN and non-200 rejection**

Run: `ENV=test pytest tests/test_ops_scripts.py -k "public_root_smoke" -q`

Expected: redirect→200 PASS；redirect→404 FAIL。

---

### Task 4: 可校验的 daily/weekly/monthly 本机恢复点与可选 COS 异地副本

**Files:**
- Create: `项目源码/wan-api/scripts/backup_database.sh`
- Modify: `项目源码/wan-api/deploy.sh`
- Modify: `项目源码/wan-api/tests/test_ops_scripts.py`

**Interfaces:**
- Consumes: `WANYU_BACKUP_BASE`（默认 `/opt/wanyu/backup`）、可选 `COS_BUCKET`、可选 `COSCLI`。
- Produces: 每个生成的 `.dump` 同目录都有基于 basename 的 `.sha256`；配置 COS 时两者都上传；未配置时明确打印 `LOCAL RECOVERY POINT ONLY`。

- [ ] **Step 1: Write failing end-to-end backup tests**

```python
def test_backup_copies_checksum_with_weekly_and_monthly_snapshots(...):
    # fake date=Sunday + day 01，fake pg_dump 输出非空 bytes。
    # 运行真实脚本，三层 dump 与三层 sidecar 均须通过 sha256sum -c。

def test_backup_uploads_dump_and_checksum_when_cos_is_configured(...):
    # fake coscli 记录调用；必须上传 daily dump 和 sidecar。
```

- [ ] **Step 2: Verify RED**

Run: `ENV=test pytest tests/test_ops_scripts.py -k "backup_" -q`

Expected: FAIL because standalone script does not exist.

- [ ] **Step 3: Implement and install the script**

`setup_backup_automation()` 用 `install -m 0750 scripts/backup_database.sh /etc/wanyu/wanyu-backup.sh`，systemd unit 增加 `EnvironmentFile=-/etc/wanyu/backup.env`；不再维护 heredoc 复制版。

- [ ] **Step 4: Verify GREEN**

Run: `ENV=test pytest tests/test_ops_scripts.py -k "backup_" -q`

Expected: PASS, including checksum verification and paired COS upload.

---

### Task 5: Restore drill 真正建库、使用正确 venv 并始终清理

**Files:**
- Modify: `项目源码/wan-api/scripts/restore_drill.sh`
- Modify: `项目源码/wan-api/tests/test_ops_scripts.py`

**Interfaces:**
- Consumes: `WANYU_BACKUP_BASE`、`WANYU_CURRENT_LINK`、`WANYU_RESTORE_DRILL_DB`，均有生产默认值。
- Produces: `DROP ... WITH (FORCE)` → `CREATE DATABASE` → `pg_restore --exit-on-error`；通过 `${CURRENT_LINK}/venv/bin/alembic heads` 获取代码 head；EXIT trap 总会清理临时库。

- [ ] **Step 1: Write failing end-to-end restore tests**

```python
def test_restore_creates_database_before_pg_restore_and_uses_release_venv(...):
    # fake pg_restore 只有看到 CREATE DATABASE marker 才成功。
    # fake alembic 只存在于 current/venv/bin/alembic。

def test_restore_drops_temporary_database_when_validation_fails(...):
    # 让行数核验失败，仍须观察到最后一次 DROP DATABASE。
```

- [ ] **Step 2: Verify RED**

Run: `ENV=test pytest tests/test_ops_scripts.py -k "restore_" -q`

Expected: current script fails before restore and cannot find `app/venv/bin/alembic`.

- [ ] **Step 3: Implement the database lifecycle**

```bash
cleanup() { sudo -u postgres psql -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"$DRILL_DB\" WITH (FORCE);" >/dev/null; }
trap cleanup EXIT
cleanup
sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$DRILL_DB\";" >/dev/null
sudo -u postgres pg_restore --exit-on-error --no-owner -d "$DRILL_DB" "$LATEST"
HEAD_REV="$(cd "$CURRENT_LINK/app" && "$CURRENT_LINK/venv/bin/alembic" heads | awk '{print $1}' | head -1)"
```

- [ ] **Step 4: Verify GREEN**

Run: `ENV=test pytest tests/test_ops_scripts.py -k "restore_" -q`

Expected: success path PASS and deliberate failure exits nonzero while cleanup PASS.

---

### Task 6: 撤回虚假验收、同步契约并发布 v17.9.19 候选状态

**Files:**
- Modify: `项目源码/wan-api/release.json`
- Modify: `项目源码/wan-api/README.md`
- Modify: `项目源码/wan-api/docs/CONTRACT.md`
- Modify: `项目源码/wan-api/docs/ops/RUNBOOK.md`
- Modify: `项目源码/deliverables/CHANGELOG.md`
- Modify: `docs/self-iterate/2026-09-07-maturity-sprint/state.json`
- Modify: `docs/self-iterate/2026-09-07-maturity-sprint/report.md`
- Modify: `docs/self-iterate/2026-09-07-maturity-sprint/verify/round-8-acceptance.md`
- Create: `docs/self-iterate/2026-09-07-maturity-sprint/verify/round-9-production-chain-repair.md`

**Interfaces:**
- Produces: API code version `v17.9.19`; `done=false` until fresh-host、生产 smoke、COS 异机 restore 均有真实日志；旧 15/15 文件保留但显式标记 `RETRACTED`。

- [ ] **Step 1: Update facts without inventing evidence**

README/CONTRACT 保持 `EXPERIMENTAL / NOT FOR PRODUCTION`；自动备份统一称“本机恢复点”，COS 未配置不得称完整灾备；S8、密钥轮换、异机恢复继续未勾选。

- [ ] **Step 2: Record the exact supersession**

`round-8-acceptance.md` 写明 v17.9.18 的 15/15 于 2026-09-08 被当前 HEAD 复审撤回，并列出 P0/P1/P2 ID；`state.json` 将 `done` 设为 false，清空 `done_evidence`，记录待现场验证项。

- [ ] **Step 3: Add local repair evidence**

`round-9-production-chain-repair.md` 只记录本轮实际命令、commit/working-tree 基线、测试计数和仍未运行的现场步骤；任何未运行步骤写 `NOT RUN`。

- [ ] **Step 4: Run document/data checks**

Run: `python -m json.tool release.json` and `python -m json.tool state.json`.

Expected: both parse; version and truth status agree.

---

### Task 7: Full verification gate

**Files:**
- Verify only; no new production behavior.

- [ ] **Step 1: Shell syntax and targeted behavior**

Run: `bash -n deploy.sh scripts/backup_database.sh scripts/restore_drill.sh scripts/upgrade_drill.sh`

Run: `ENV=test pytest tests/test_ops_scripts.py -q`

- [ ] **Step 2: Existing API regression suite**

Run: `ENV=test pytest tests/ -q`

- [ ] **Step 3: Static and repository checks**

Run: `ruff check app tests --select E9,F63,F7,F82 --ignore E402`

Run: `git diff --check`

Run: `git status --short`

- [ ] **Step 4: Evidence boundary**

Only claim local completion if every command above exits 0. Report fresh-host deploy, production deploy, offsite upload, and offsite restore as unverified until their real host commands and logs exist.

## Self-Review

- Spec coverage: P0-1→Task 2；P0-2→Task 3；P1-1→Task 5；P1-2→Task 6；P1-3→Tasks 4/6；P2-1→Task 4；P2-2→Task 2。
- Placeholder scan: no TBD/TODO/“later” implementation placeholders remain;现场步骤 are explicitly evidence-gated rather than deferred implementation.
- Interface consistency: deploy uses `load_release_metadata()` before `setup_secret_env()`; both CLI modes call `build_release()`; backup/restore test overrides use the same `WANYU_*` names documented above.
