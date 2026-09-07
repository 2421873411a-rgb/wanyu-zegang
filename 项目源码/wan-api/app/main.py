from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.database import init_db, close_db
from app.api.v1 import auth, jobs, user, cycles, salary, audit, admin


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
    """健康检查（携带版本：deploy smoke 靠它证明新代码真正生效）"""
    return {"status": "ok", "version": settings.APP_VERSION}
