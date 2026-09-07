# 皖域 API 运维手册（RUNBOOK）

## 部署前置（全新机器）

- 支持矩阵：Ubuntu 24.04–25.x（deploy.sh 读取 /etc/os-release 硬校验；python3.12 apt 包名钉死，22.04 需 PPA 不支持）。
- 静态数据必须先于部署就位：`/opt/wanyu/static/maintainable/data/` 下含
  `cycles/{2024,2025,2026}/jobs.json`、`salary/anhui.json`、`audit/review-queue.json`
  （来源：网站构建产物）。deploy.sh 在 check_prerequisites 阶段即校验该目录，缺失立即中止。
- DNS：wan.kaogong.art 的 A 记录需已指向本机（smoke 断言公网 HTTPS 与 301 强跳）。

## 回滚（deploy.sh 失败或新版本异常时）

deploy.sh 每次换血前会把旧版本代码备份到服务器 `/opt/wanyu/backup/<时间戳>/`（不含 venv 与 .env），
`/opt/wanyu/backup/LATEST` 记录最近一次备份时间戳；迁移升级前的 alembic 版本戳写在
`/opt/wanyu/backup/<时间戳>/alembic-before.txt`。

⚠️ **顺序铁律（v17.9.12 修正）**：必须**先降数据库、后回滚代码**。
旧代码的 migrations 目录里没有新 revision，先 rsync 旧代码再 downgrade 会报
"Can't locate revision"——恰在最需要回滚的时刻走不通。

1. 回滚数据库（先做；用"当前仍在位的新代码"执行 downgrade）：
   ```bash
   ts=$(cat /opt/wanyu/backup/LATEST)
   cat /opt/wanyu/backup/$ts/alembic-before.txt   # 确认旧版本号
   cd /opt/wanyu/api && source venv/bin/activate
   alembic downgrade <旧版本号>
   ```
   数据已损坏时的彻底恢复：`pg_dump` 快照（deploy.sh 迁移前自动生成并校验非空）→
   `sudo -u postgres pg_restore -d wanyu_db --clean --if-exists <快照文件>`。
2. 回滚代码：
   ```bash
   rsync -a --delete --exclude 'venv' --exclude '.env' /opt/wanyu/backup/$ts/ /opt/wanyu/api/
   # .env 不随回滚（rsync 排除），其 APP_VERSION 仍是新值——旧代码读它会把
   # /health 报成新版本。回滚后把 .env 对齐旧版本再重启：
   ver=$(python3 -c "import json;print(json.load(open('/opt/wanyu/api/release.json'))['release'])")
   sed -i "s/^APP_VERSION=.*/APP_VERSION=$ver/" /opt/wanyu/api/.env
   systemctl restart wanyu-api
   curl -sf http://127.0.0.1:8000/health
   ```
   venv 无需重建（依赖按 runtime lock 安装，回滚目标版本的 lock 与现 venv 一致时可复用；
   若回滚跨越依赖变更，删掉 venv 后 `python3.12 -m venv venv && venv/bin/pip install -r requirements.lock.txt`）。
3. 数据库快照（每次部署前强制）：
   ```bash
   sudo -u postgres pg_dump -Fc wanyu_db > /opt/wanyu/backup/wanyu_db-$(date +%Y%m%d-%H%M%S).dump
   ```

## 管理员引导

部署链只在设置了 `ADMIN_BOOTSTRAP_PASSWORD` 时自动创建管理员；否则完成横幅会提示手动执行：
```bash
cd /opt/wanyu/api && source venv/bin/activate
python scripts/create_admin.py --email admin@kaogong.art --username admin
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
