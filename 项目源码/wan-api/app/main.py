import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi import HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.middleware import RequestContextMiddleware
from app.observability import metrics
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.config import settings
from app.database import engine, init_db, close_db
from app.api.v1 import auth, jobs, user, cycles, salary, audit, admin

# v17.9.12：app 级日志显式落 stderr（gunicorn capture_output 收集）——
# 此前唯一的审计日志（admin 导入 INFO）因无 handler 被 Python 静默丢弃。
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    await init_db()
    yield
    # 关闭时清理资源
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="皖域择岗 API - 安徽公务员/事业编岗位信息服务平台",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# v17.10.0 请求上下文：request-id 透回 + 结构化访问日志 + 进程内指标。
# 后注册 = 最外层，CORS 拒绝响应也带 X-Request-ID。
app.add_middleware(RequestContextMiddleware)


@app.get("/metrics", include_in_schema=False)
async def metrics_endpoint(request: Request):
    """Prometheus 文本指标（v17.10.0）。

    仅 METRICS_TOKEN 配置时可用（Bearer 认证）；未配置一律 404——不泄漏端点存在。
    多 worker 下各进程独立计数，抓取端需按实例聚合。
    """
    token = settings.METRICS_TOKEN
    if not token or request.headers.get("authorization") != f"Bearer {token}":
        raise HTTPException(status_code=404)
    return Response(content=metrics.render(), media_type="text/plain; version=0.0.4; charset=utf-8")

# 注册路由
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["岗位"])
app.include_router(user.router, prefix="/api/v1/user", tags=["用户工作台"])
app.include_router(cycles.router, prefix="/api/v1/cycles", tags=["周期"])
app.include_router(salary.router, prefix="/api/v1/salary", tags=["待遇"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["审计"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["管理后台"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/docs"
    }


@app.get("/health")
async def health():
    """健康检查（readiness 语义：含 DB 探活与版本）。

    v17.9.12：此前 DB 宕机仍返回 200，部署 smoke 与探针全绿、故障只能等用户报障。
    DB 不可达 → 503（版本字段保留，便于排障）。
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "version": settings.APP_VERSION, "db": "unreachable"},
        )
    return {"status": "ok", "version": settings.APP_VERSION, "db": db_status}
