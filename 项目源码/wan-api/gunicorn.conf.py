"""
Gunicorn配置文件
用于生产环境部署FastAPI应用
"""
import multiprocessing
import os

# 绑定地址
bind = "127.0.0.1:8000"

# Worker配置
# 4核CPU: 2 * 4 + 1 = 9，但考虑到内存限制，使用较少的worker
workers = min(multiprocessing.cpu_count() * 2 + 1, 4)
worker_class = "uvicorn.workers.UvicornWorker"
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
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程配置
pidfile = "/var/run/wanyu/gunicorn.pid"
user = "www-data"
group = "www-data"

# 安全配置
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# 内存限制
# worker_tmp_dir = "/dev/shm"  # 使用共享内存提高性能

def on_starting(server):
    """服务器启动时的回调"""
    # 确保日志目录存在
    log_dir = "/var/log/wanyu"
    pid_dir = "/var/run/wanyu"
    
    for directory in [log_dir, pid_dir]:
        os.makedirs(directory, exist_ok=True)
    
    # 设置日志文件权限
    for log_file in ["/var/log/wanyu/gunicorn-access.log", "/var/log/wanyu/gunicorn-error.log"]:
        if not os.path.exists(log_file):
            open(log_file, 'w').close()
            os.chmod(log_file, 0o644)

def post_fork(server, worker):
    """Worker fork后的回调"""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_exec(server):
    """主进程fork前的回调"""
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    """服务器准备好接受连接时的回调"""
    server.log.info("Server is ready. Spawning workers...")
