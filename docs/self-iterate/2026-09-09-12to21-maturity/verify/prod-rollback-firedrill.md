== 实弹前状态 ==
/opt/wanyu/releases/v17.9.22-nodata
{"status":"ok","version":"v17.9.22","db":"ok"}
[0;31m[ERROR][0m 自动回滚：current -> v17.9.21-nodata
[0;31m[ERROR][0m ✓ 已回滚至 v17.9.21-nodata（version=v17.9.21），服务健康
== 实弹后状态 ==
/opt/wanyu/releases/v17.9.21-nodata
{"status":"ok","version":"v17.9.21","db":"ok"}
grep: /etc/wanyu/wanyu.env: Permission denied
[1;33m[WARN][0m 未设置 ADMIN_BOOTSTRAP_PASSWORD，跳过管理员引导。生产管理员必须补做：
[1;33m[WARN][0m   cd /opt/wanyu/current/app && sudo -u www-data /opt/wanyu/current/venv/bin/python scripts/create_admin.py --email admin@kaogong.art --username admin
[0;32m[INFO][0m 部署完成：current -> /opt/wanyu/releases/v17.9.22-nodata
[0;32m[INFO][0m API https://wan.kaogong.art/api/docs · health https://wan.kaogong.art/health
== 终态 ==
/opt/wanyu/releases/v17.9.22-nodata
{"status":"ok","version":"v17.9.22","db":"ok"}
0
