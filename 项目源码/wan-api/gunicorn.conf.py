"""Gunicorn 配置。

v17.9.1 说明：access_log_format 移除 %(r)s/%(q)s——完整 request line 会把
query string 写进访问日志（token 泄漏面）；凭证一律走 body，路径最小化记录。
"""
import multiprocessing
import os

# 绑定地址
bind = "127.0.0.1:8000"

# Worker配置
# 4核CPU: 2 * 4 + 1 = 9，但考虑到内存限制，使用较少的worker
# 默认 1：memory 限流后端按单 worker 设计；RATE_LIMIT_BACKEND=redis 后可提高
workers = int(os.environ.get("WANYU_WEB_CONCURRENCY", 1))
# nginx 同机反代：显式钉死受信代理，防上游版本升级改变 X-Forwarded-For 解析行为
forwarded_allow_ips = "127.0.0.1"
worker_class = "uvicorn_worker.UvicornWorker"
worker_connections = 1000

# 超时配置
timeout = 120
graceful_timeout = 30
keepalive = 5

# 请求限制
max_requests = 1000
max_requests_jitter = 50

# 日志配置
accesslog = "/var/log/wanyu/gunicorn-access.log"
errorlog = "/var/log/wanyu/gunicorn-error.log"
loglevel = "info"
# app 的 stdout/stderr（含 v17.9.12 起的 app 级审计日志）转发进 errorlog
capture_output = True
# 最小化访问日志：仅方法/路径/协议，不记录 query string（token 不进日志）
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(m)s %(U)s %(H)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
