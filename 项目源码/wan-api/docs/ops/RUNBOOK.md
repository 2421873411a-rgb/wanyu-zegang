# 皖域 API 运维手册（RUNBOOK）

## 部署前置（全新机器）

- 支持矩阵：Ubuntu 24.04–25.x（deploy.sh 读取 /etc/os-release 硬校验；python3.12 apt 包名钉死，22.04 需 PPA 不支持）。
- 静态数据必须先于部署就位：默认 `/var/www/wan.kaogong.art/maintainable/data/` 下含
  `cycles/{2024,2025,2026}/jobs.json`、`salary/anhui.json`、`audit/review-queue.json`
  （来源：网站构建产物）。如需改路径，显式设置 `STATIC_DATA_PATH`；deploy.sh 在
  check_prerequisites 阶段即校验该目录，缺失立即中止。
- DNS：wan.kaogong.art 的 A 记录需已指向本机（smoke 断言公网 HTTPS 与 301 强跳）。

## 架构（v17.9.19 Immutable Release）

- 代码与 venv：`/opt/wanyu/releases/<版本>-<sha>/{app,venv}`——每次部署全新目录+全新 venv
  （root 属主，www-data 只读），`/opt/wanyu/current` 符号链接原子切换。
  服务器文件系统 == Git release：无覆盖残留/幽灵文件，无跨版本依赖漂移。
- 生产 secret：`/etc/wanyu/wanyu.env`（root:www-data 0640，与代码目录彻底分离）。
- 运行时可写面仅 `/var/log/wanyu`（systemd ReadWritePaths 唯一写点）。
- DB **本机恢复点**：`wanyu-backup.timer`（daily 03:00；每个 daily/weekly/monthly dump
  都有同目录 checksum；本机保留 7/4/3）。未配置 COS 时不能称为完整灾备。
- 可选异地副本：`/etc/wanyu/backup.env` 配置 COS 后，timer 会把新生成的各层 dump 与
  checksum 成对上传；对象存储必须另开版本化/保留策略，见下文。
- 恢复演练：`bash /opt/wanyu/current/app/scripts/restore_drill.sh`（checksum→建临时库→
  pg_restore→代码 head/行数对账→成功或失败均清理）。
- 升级漂移演练：`bash scripts/upgrade_drill.sh`（幽灵文件/依赖漂移/幂等/回滚切换四不变量）。

## 回滚（deploy.sh 失败或新版本异常时）

deploy.sh 在迁移前生成 `/opt/wanyu/backup/wanyu_db-<时间>.dump`、配对 `.sha256` 和
`.alembic-before.txt`；导入后另生成 `wanyu_db-post-import-<时间>.dump` 与 checksum。
代码回滚依赖 `/opt/wanyu/releases/` 保留的前一 release，不再使用旧覆盖式目录或 `LATEST`。

⚠️ **顺序铁律**：遇到不兼容迁移时必须**先用当前新 release 降数据库、后切旧 release**。
旧代码的 migrations 目录里没有新 revision，先切旧代码再 downgrade 会报
"Can't locate revision"——恰在最需要回滚的时刻走不通。

1. 找到迁移前 revision（与 dump 同名的 sidecar），并用当前新 release 执行 downgrade：
   ```bash
   snapshot=/opt/wanyu/backup/wanyu_db-<时间>.dump
   old_rev=$(cat "$snapshot.alembic-before.txt")
   sudo env OLD_REV="$old_rev" /bin/bash -c '
     cd /opt/wanyu/current/app
     source ./deploy.sh
     run_as_app /opt/wanyu/current/venv/bin/alembic downgrade "$OLD_REV"
   '
   ```
   若 sidecar 为 `base`，表示迁移前没有 Alembic schema；不要盲目执行，先按快照恢复流程处理。
2. 原子切回上一 release，并把外部 EnvironmentFile 的版本同步为旧 release：
   ```bash
   old=/opt/wanyu/releases/<旧release目录>
   old_ver=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["release"])' "$old/app/release.json")
   sudo ln -sfn "$old" /opt/wanyu/current.tmp
   sudo mv -T /opt/wanyu/current.tmp /opt/wanyu/current
   sudo sed -i "s/^APP_VERSION=.*/APP_VERSION=$old_ver/" /etc/wanyu/wanyu.env
   sudo systemctl restart wanyu-api
   curl -sf http://127.0.0.1:8000/health
   ```
3. 数据已损坏时，先停服务并保留事故现场 dump，再恢复已校验快照：
   ```bash
   sudo systemctl stop wanyu-api
   sudo -u postgres pg_dump -Fc wanyu_db > /opt/wanyu/backup/incident-before-restore.dump
   (cd /opt/wanyu/backup && sha256sum -c <快照名>.dump.sha256)
   sudo -u postgres pg_restore --exit-on-error --clean --if-exists --no-owner \
     -d wanyu_db /opt/wanyu/backup/<快照名>.dump
   sudo systemctl start wanyu-api
   ```

## DB 异地副本（完整灾难恢复的必要条件）

1. 在服务器安装并初始化 `coscli`；凭据只留服务器，禁止写仓库或交接包。
2. 新建 root-only 配置：
   ```bash
   sudo install -m 0600 /dev/null /etc/wanyu/backup.env
   sudo sh -c 'printf "%s\n" \
     "COS_BUCKET=<私有桶名-APPID>" \
     "COSCLI=/usr/local/bin/coscli" \
     "COS_PREFIX=wanyu-db" > /etc/wanyu/backup.env'
   sudo systemctl start wanyu-backup.service
   sudo journalctl -u wanyu-backup.service -n 50 --no-pager
   ```
3. 在 COS 控制台启用版本化与保留/防删策略；仅“上传成功”不足以证明整机灾难恢复。
4. 从另一台机器下载同一 dump 与 `.sha256` 到隔离目录，先执行 `sha256sum -c`，再把它放入
   `<临时根>/daily/` 并运行：
   ```bash
   sudo WANYU_BACKUP_BASE=<临时根> \
     WANYU_CURRENT_LINK=/opt/wanyu/current \
     bash /opt/wanyu/current/app/scripts/restore_drill.sh
   ```
   保存完整输出、机器、时间、commit/release 和对象版本号后，才能勾选 CONTRACT 的异机恢复门禁。

## 管理员引导

部署链只在设置了 `ADMIN_BOOTSTRAP_PASSWORD` 时自动创建管理员；否则完成横幅会提示手动执行：
```bash
sudo /bin/bash -c '
  cd /opt/wanyu/current/app
  source ./deploy.sh
  run_as_app /opt/wanyu/current/venv/bin/python scripts/create_admin.py \
    --email admin@kaogong.art --username admin
'
```
注册接口永远只产生普通用户（v17.9.1 S0 纪律），管理员只能由此脚本产生。

## 版本证明

`/health` 返回 `version` 字段 = 部署时从 `wan-api/release.json`（wanyu-api-release/v1）注入 .env 的 `APP_VERSION`。
deploy.sh 的 smoke 会断言 `/health` 版本 == 部署版本，`systemctl restart` 落空会在此暴露。

## 日常核对

- `systemctl status wanyu-api`（active/running）
- `curl -s http://127.0.0.1:8000/health`
- `curl -s "http://127.0.0.1:8000/api/v1/jobs/search?page_size=1"` → total 应为 28568（2024+2025+2026 active 口径）
- 日志：`/var/log/wanyu/gunicorn-*.log`（www-data:750）

## 密钥轮换 runbook（v17.9.23；只写步骤不写值）

1. **SSH 私钥**（已完成 2026-09-08）：ed25519 新钥已入 `authorized_keys` 并验证连通，
   旧 wanyu111 已移除；腾讯云平台层注入的 `skey-*` 解绑仍属控制台待办。
2. **SECRET_KEY**（影响面：所有 access/refresh token 立即失效，全部用户需重新登录）：
   ```bash
   # 1) 生成新值（≥32 字符，禁止使用历史值/公开样例）
   openssl rand -hex 32
   # 2) 写入独立 secret 文件（保持 640 root:www-data）
   sudo sed -i "s/^SECRET_KEY=.*/SECRET_KEY=<新值>/" /etc/wanyu/wanyu.env
   # 3) 重启并验证（/health 200；旧 token 401 属预期）
   sudo systemctl restart wanyu-api && curl -sf http://127.0.0.1:8000/health
   ```
   轮换后删除本机 shell 历史（`history -c`），新值不入任何仓库/聊天/工单。
3. **管理员密码**：`scripts/create_admin.py --promote <邮箱>` 管升权；改密走「删旧建新」：
   先用 `--email/--username/--password` 建好新管理员并登录验证，再降权/禁用旧账号
   （最后管理员保护生效中，不可直接禁用唯一管理员）。凭据文件
   `/opt/wanyu/credentials/admin.txt`（600）同步更新。
4. **依赖漏洞**：每周一 CI `security-scan`（schedule）跑 pip-audit 双 lock 并产 SBOM
   artifact（wanyu-api-sbom，保留 90 天）；红即修（升级 lock → 全量门禁 → 发布）。
