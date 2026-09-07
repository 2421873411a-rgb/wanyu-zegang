# 皖域 API 运维手册（RUNBOOK）

## 回滚（deploy.sh 失败或新版本异常时）

deploy.sh 每次换血前会把旧版本代码备份到服务器 `/opt/wanyu/backup/<时间戳>/`（不含 venv 与 .env），
`/opt/wanyu/backup/LATEST` 记录最近一次备份时间戳；迁移升级前的 alembic 版本戳写在
`/opt/wanyu/backup/<时间戳>/alembic-before.txt`。

1. 回滚代码：
   ```bash
   ts=$(cat /opt/wanyu/backup/LATEST)
   rsync -a --delete --exclude 'venv' --exclude '.env' /opt/wanyu/backup/$ts/ /opt/wanyu/api/
   systemctl restart wanyu-api
   curl -sf http://127.0.0.1:8000/health   # 核对 version 字段回到旧版本
   ```
   venv 无需重建（依赖按 runtime lock 安装，回滚目标版本的 lock 与现 venv 一致时可复用；
   若回滚跨越依赖变更，删掉 venv 后 `python3.12 -m venv venv && venv/bin/pip install -r requirements.lock.txt`）。
2. 回滚数据库（仅当新版本包含已升级的迁移且旧代码不兼容新表结构时）：
   ```bash
   cat /opt/wanyu/backup/$ts/alembic-before.txt   # 确认旧版本号
   cd /opt/wanyu/api && source venv/bin/activate
   alembic downgrade <旧版本号>
   ```
   更彻底的恢复：`pg_dump` 备份（部署前必须先做，见下）→ `psql` 恢复。
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

`/health` 返回 `version` 字段 = 部署时从 `项目源码/release.json` 注入 .env 的 `APP_VERSION`。
deploy.sh 的 smoke 会断言 `/health` 版本 == 部署版本，`systemctl restart` 落空会在此暴露。

## 日常核对

- `systemctl status wanyu-api`（active/running）
- `curl -s http://127.0.0.1:8000/health`
- `curl -s "http://127.0.0.1:8000/api/v1/jobs/search?page_size=1"` → total 应为 28568（2024+2025+2026 active 口径）
- 日志：`/var/log/wanyu/gunicorn-*.log`（www-data:750）
