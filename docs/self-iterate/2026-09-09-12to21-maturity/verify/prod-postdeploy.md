== 公网验证 2026-09-09 07:17:43 ==
-- health --
{"status":"ok","version":"v17.9.21","db":"ok"}
-- search 2026 total --
8401
-- all-cycle total --
28568
-- HTTPS / 状态与跳转目标 --
200 -> 
-- HTTP / 期望 301 --
301
-- 静态入口 --
200
== 认证链路 2026-09-09 07:18:06 ==
register: 201
login tokens: access=187ch refresh=312ch
Traceback (most recent call last):
  File "<string>", line 1, in <module>
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/me.json'
me: 200 
refresh rotated: yes
old refresh reuse (期望 401): 401
logout: 204
-- admin login (凭据不回显) --
admin login: 200
is_admin: True
-- unit 加固 --
NoNewPrivileges=yes
ProtectSystem=strict
PrivateTmp=true
ReadWritePaths=/var/log/wanyu
-- journalctl 错误扫描 --
0
0
-- 磁盘 --
29G free
== 公网终验 2026-09-09 07:38:03 ==
{"status":"ok","version":"v17.9.22","db":"ok"}
total: 28568
HTTPS root: 200
