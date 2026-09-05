from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "皖域择岗 API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # 数据库配置（本地开发使用SQLite，生产环境使用PostgreSQL）
    DATABASE_URL: str = "sqlite+aiosqlite:///./wanyu.db"
    DATABASE_ECHO: bool = False
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS配置
    CORS_ORIGINS: List[str] = ["https://wan.kaogong.art", "http://localhost:8765"]
    
    # 静态数据路径（用于数据导入）
    STATIC_DATA_PATH: str = "/opt/wanyu/static/maintainable/data"
    
    # 注册配置
    ALLOW_REGISTRATION: bool = True
    ADMIN_EMAIL: str = ""
    
    # 分页配置
    DEFAULT_PAGE_SIZE: int = 60
    MAX_PAGE_SIZE: int = 200
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
