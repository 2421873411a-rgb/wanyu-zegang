# v17.9.19 Production Chain Repair Evidence

## 证据边界

- 基线：`main@7c2d011917482ae7cf5d1c7285094b74d6bf7c23`。
- 工作分支：`codex/fix-v17.9.19-production-chain`。
- 本记录只证明仓库内代码与临时目录 shell 行为；不把本机替身测试写成 Ubuntu fresh-host、
  生产部署、COS 上传或异机恢复。

## 已复现并修复

| ID | 旧行为（RED） | 修复后门禁 |
|---|---|---|
| R9-1 | source deploy.sh 直接启动 root 部署 | source 无副作用，CLI dispatch 独立 |
| R9-2 | secret 写入时仍看到 stale/空 APP_VERSION | `load_release_metadata` 先于 secret |
| R9-3 | build-only 没有统一构建入口 | 生产/演练都调用 `build_release()` |
| R9-4 | fresh-host 302 被当成失败 | HTTPS 跟随跳转后必须最终 200 |
| R9-5 | 运维 CLI 不加载外部 EnvironmentFile | `run_as_app` 与 systemd 共享 `/etc/wanyu/wanyu.env` |
| R9-6 | weekly/monthly 缺 checksum | 三层 dump/sidecar 成对复制且各自可校验 |
| R9-7 | restore 未建库且 venv 路径错误 | DROP→CREATE→restore；`current/venv/bin/alembic heads` |
| R9-8 | restore 失败遗留临时库 | EXIT trap；突变禁用 trap 时回归测试确实失败 |
| R9-9 | 迁移锚点依赖旧 `LATEST` 路径 | 原子 dump + checksum + 同名 revision sidecar |
| R9-10 | fresh-host 模板使用 `alias + try_files` | 恢复 CONTRACT 要求的 `root + try_files` |

## 当前仓库验证

- 修改前基线：`ENV=test python -m pytest -q` → `78 passed, 5 skipped`。
- 运维行为门禁：`ENV=test python -m pytest tests/test_ops_scripts.py -q` → `19 passed in 23.55s`。
- 部署联动回归：`ENV=test python -m pytest tests/test_deploy_linkage.py -q` → `12 passed in 3.69s`。
- 完整 API 回归：`ENV=test python -m pytest -q` → `97 passed, 5 skipped in 99.36s`。
- Bash 语法：`bash -n deploy.sh scripts/backup_database.sh scripts/restore_drill.sh scripts/upgrade_drill.sh` → PASS。
- Ruff：`python -m ruff check app tests --select E9,F63,F7,F82 --ignore E402` → PASS。
- JSON：`release.json`、`state.json` → PASS。
- `git diff --check` → PASS。

## 尚未运行（不得写 PASS）

- `NOT RUN`：全新 Ubuntu 24.04 主机完整 `deploy.sh`。
- `NOT RUN`：真实证书签发后的 HTTP 301、HTTPS 302→200、公网 API smoke。
- `NOT RUN`：生产 PostgreSQL dump 的真实 restore drill。
- `NOT RUN`：COS 私有桶上传、版本化/保留策略、另一台机器下载与 restore drill。
- `NOT RUN`：v17.9.19 生产部署和回滚。
