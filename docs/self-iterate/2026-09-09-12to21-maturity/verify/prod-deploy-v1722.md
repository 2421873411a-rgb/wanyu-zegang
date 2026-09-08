[0;32m[INFO][0m 开始部署皖域择岗 API（Immutable Release）...
[0;32m[INFO][0m ✓ 静态数据前置完整（三周期 jobs + salary + audit）
[0;32m[INFO][0m 安装系统依赖...

WARNING: apt does not have a stable CLI interface. Use with caution in scripts.

Hit:1 http://mirrors.tencentyun.com/ubuntu noble InRelease
Hit:2 http://mirrors.tencentyun.com/ubuntu noble-updates InRelease
Hit:3 http://mirrors.tencentyun.com/ubuntu noble-backports InRelease
Hit:4 http://mirrors.tencentyun.com/ubuntu noble-security InRelease
Reading package lists...
Building dependency tree...
Reading state information...
186 packages can be upgraded. Run 'apt list --upgradable' to see them.

WARNING: apt does not have a stable CLI interface. Use with caution in scripts.

Reading package lists...
Building dependency tree...
Reading state information...
python3.12 is already the newest version (3.12.3-1ubuntu0.16).
python3.12-venv is already the newest version (3.12.3-1ubuntu0.16).
python3-pip is already the newest version (24.0+dfsg-1ubuntu1.3).
postgresql is already the newest version (16+257build1.1).
postgresql-contrib is already the newest version (16+257build1.1).
redis-server is already the newest version (5:7.0.15-1ubuntu0.24.04.4).
nginx is already the newest version (1.24.0-2ubuntu7.17).
certbot is already the newest version (2.9.0-1).
python3-certbot-nginx is already the newest version (2.9.0-1).
curl is already the newest version (8.5.0-2ubuntu10.13).
sudo is already the newest version (1.9.15p5-3ubuntu5.24.04.2).
The following packages were automatically installed and are no longer required:
  libblas3 libgfortran5 liblapack3 python3-deprecated python3-jwcrypto
  python3-numpy python3-websockify python3-wrapt
Use 'sudo apt autoremove' to remove them.
0 upgraded, 0 newly installed, 0 to remove and 186 not upgraded.
Synchronizing state of postgresql.service with SysV service script with /usr/lib/systemd/systemd-sysv-install.
Executing: /usr/lib/systemd/systemd-sysv-install enable postgresql
Synchronizing state of redis-server.service with SysV service script with /usr/lib/systemd/systemd-sysv-install.
Executing: /usr/lib/systemd/systemd-sysv-install enable redis-server
Synchronizing state of nginx.service with SysV service script with /usr/lib/systemd/systemd-sysv-install.
Executing: /usr/lib/systemd/systemd-sysv-install enable nginx
[0;32m[INFO][0m 配置 PostgreSQL 数据库...
[0;32m[INFO][0m wanyu_user 已存在，保留既有凭据
NOTICE:  extension "pgcrypto" already exists, skipping
NOTICE:  extension "pg_trgm" already exists, skipping
[0;32m[INFO][0m 构建 release v17.9.22...
No broken requirements found.
[0;32m[INFO][0m ✓ release 构建完成（全新目录/全新 venv，root:root 只读）
[0;32m[INFO][0m 配置 systemd 服务...
[0;32m[INFO][0m 配置日志轮转...
[0;32m[INFO][0m ✓ DB 备份定时器已启用（daily 03:00，7daily/4weekly/3monthly）
[0;32m[INFO][0m 已停止 wanyu-api（部署窗口开始）
[0;32m[INFO][0m ✓ current -> /opt/wanyu/releases/v17.9.22-nodata
[0;32m[INFO][0m 导入数据（使用新 release venv）...
[0;32m[INFO][0m ✓ 数据库快照：/opt/wanyu/backup/wanyu_db-20260909-073614.dump
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
导入结果: {'cycle_2024': {'imported': 0, 'updated': 10017, 'deactivated': 0, 'active_rows': 10017, 'incoming_rows': 10017, 'existing_rows': 10017, 'job_id_set_sha256': '0cbe022e2fda407fcf674f22bc8538b9d26a82147daa386391dff397dc25c207'}, 'cycle_2025': {'imported': 0, 'updated': 10150, 'deactivated': 0, 'active_rows': 10150, 'incoming_rows': 10150, 'existing_rows': 10150, 'job_id_set_sha256': '91d1355e9a6ac0225f063913ac6cca173287df29ff2faa0337a94d25221c7948'}, 'cycle_2026': {'imported': 0, 'updated': 8511, 'deactivated': 0, 'active_rows': 8401, 'incoming_rows': 8511, 'existing_rows': 8511, 'job_id_set_sha256': '230697a751445824407aa6b9630776f43df726a47faf5cf2e253c4d987c0e12a'}, 'salary': {'imported': 160}, 'review_events': {'imported': 7}}
[0;32m[INFO][0m ✓ 导入后快照：/opt/wanyu/backup/wanyu_db-post-import-20260909-073621.dump
[0;32m[INFO][0m 启动服务...
● wanyu-api.service - WanYu Job API (FastAPI + Gunicorn, immutable release)
     Loaded: loaded (/etc/systemd/system/wanyu-api.service; enabled; preset: enabled)
     Active: active (running) since Wed 2026-09-09 07:36:21 CST; 24ms ago
[0;32m[INFO][0m 部署后 smoke 测试...
[0;32m[INFO][0m ✓ 健康/版本(v17.9.22)/岗位(8401) smoke 全通过
[1;33m[WARN][0m 未设置 ADMIN_BOOTSTRAP_PASSWORD，跳过管理员引导。生产管理员必须补做：
[1;33m[WARN][0m   cd /opt/wanyu/current/app && sudo -u www-data /opt/wanyu/current/venv/bin/python scripts/create_admin.py --email admin@kaogong.art --username admin
[0;32m[INFO][0m 部署完成：current -> /opt/wanyu/releases/v17.9.22-nodata
[0;32m[INFO][0m API https://wan.kaogong.art/api/docs · health https://wan.kaogong.art/health
