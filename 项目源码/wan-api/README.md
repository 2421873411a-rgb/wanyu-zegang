# 皖域择岗 API

> ⚠️ **EXPERIMENTAL / NOT FOR PRODUCTION**：wan-api 处于原型态，
> 安全与测试门禁见 `docs/CONTRACT.md`；满足上线前置前不得对公网开放。


基于 FastAPI 的动态网站后端，为皖域择岗静态站提供用户系统、数据管理和搜索功能。

## 功能特性

- **用户系统**：注册/登录、JWT认证、收藏/快照云端同步
- **岗位搜索**：全文搜索、多维筛选、分页查询
- **数据管理**：后台管理界面、数据导入导出
- **API文档**：自动生成的Swagger/ReDoc文档

## 技术栈

- **后端框架**：FastAPI >=0.141.1
- **数据库**：PostgreSQL 16 + SQLAlchemy 2.0
- **缓存**：Redis
- **认证**：JWT + OAuth2
- **部署**：Gunicorn + Nginx + systemd

## 项目结构

```
wan-api/
├── app/
│   ├── api/v1/           # API路由
│   │   ├── auth.py       # 认证接口
│   │   ├── jobs.py       # 岗位接口
│   │   ├── user.py       # 用户工作台接口
│   │   ├── cycles.py     # 周期接口
│   │   ├── salary.py     # 待遇接口
│   │   ├── audit.py      # 审计接口
│   │   └── admin.py      # 管理后台接口
│   ├── models/           # 数据库模型
│   ├── schemas/          # Pydantic验证模型
│   ├── services/         # 业务服务
│   ├── utils/            # 工具函数
│   ├── config.py         # 配置文件
│   ├── database.py       # 数据库连接
│   ├── dependencies.py   # 依赖注入
│   └── main.py           # 应用入口
├── migrations/           # Alembic数据库迁移
├── tests/                # 门禁式测试套件（pytest；见 docs/CONTRACT.md §4）
├── scripts/              # 运维脚本（create_admin.py 等）
├── docs/                 # 契约与说明（CONTRACT.md）
├── gunicorn.conf.py      # Gunicorn配置
├── requirements.txt      # Python依赖
├── deploy.sh             # 部署脚本
└── start.sh              # 开发启动脚本
```

## 快速开始

### 1. 环境准备

```bash
# 安装Python 3.12
sudo apt install python3.12 python3.12-venv

# 创建虚拟环境
python3.12 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
# 编辑 .env 文件配置数据库等信息
```

### 3. 启动开发服务器

```bash
# 启动FastAPI开发服务器
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 或使用启动脚本
./start.sh
```

### 4. 访问API文档

- Swagger UI: http://127.0.0.1:8000/api/docs
- ReDoc: http://127.0.0.1:8000/api/redoc

## 生产部署

### 自动部署

```bash
# 使用部署脚本（需要root权限）
sudo ./deploy.sh
```

### 手动部署

```bash
# 1. 安装依赖
sudo apt install postgresql redis-server nginx

# 2. 配置数据库
sudo -u postgres createuser -P wanyu_user
sudo -u postgres createdb -O wanyu_user wanyu_db

# 3. 配置环境变量
export DATABASE_URL=postgresql+asyncpg://wanyu_user:password@localhost:5432/wanyu_db

# 4. 运行数据库迁移
alembic upgrade head

# 5. 启动Gunicorn
gunicorn app.main:app -c gunicorn.conf.py
```

## API接口

### 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册 |
| POST | `/api/v1/auth/login` | 用户登录 |
| GET | `/api/v1/auth/me` | 获取当前用户 |

### 岗位接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/jobs/search` | 搜索岗位 |
| GET | `/api/v1/jobs/{record_id}` | 岗位详情 |
| GET | `/api/v1/jobs/stats/by-city` | 城市统计 |

### 用户工作台接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/user/positions` | 我的收藏 |
| POST | `/api/v1/user/positions` | 添加收藏 |
| DELETE | `/api/v1/user/positions/{record_id}` | 取消收藏 |

## 数据导入

### 导入JSON数据

```python
import asyncio
from app.database import init_db, async_session_factory
from app.services.import_service import import_all_data

async def main():
    await init_db()
    async with async_session_factory() as db:
        results = await import_all_data(db)
        print('导入结果:', results)

asyncio.run(main())
```

### 导入单个文件

```python
from app.services.import_service import ImportService, load_json_file

async def import_jobs():
    data = await load_json_file('path/to/jobs.json')
    service = ImportService(db)
    stats = await service.import_cycle_jobs('2026', data)
```

## 测试

> v17.9.1 起 tests/ 为真实存在的门禁式套件（21 用例），覆盖：
> 注册不可成为管理员 / 生产 SECRET_KEY 拒绝启动 / refresh 仅 body + 轮换撤销 /
> 重复收藏数据库拒绝 / 对比≤4 / 管理导入真实写库对账 / 最后管理员保护 / 413 / 登出。
> 契约详见 `docs/CONTRACT.md`。

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_auth.py

# 运行带覆盖率的测试
pytest --cov=app tests/
```

## 配置说明

### 数据库配置

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
```

### JWT配置

```env
SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```

### Redis配置

```env
REDIS_URL=redis://localhost:6379/0
```

## 常见问题

### 1. 数据库连接失败

检查PostgreSQL服务是否运行：
```bash
sudo systemctl status postgresql
```

### 2. 端口被占用

修改Gunicorn配置或使用不同端口：
```bash
gunicorn app.main:app --bind 127.0.0.1:8001
```

### 3. 权限问题

确保日志目录和PID目录存在且有写入权限：
```bash
sudo mkdir -p /var/log/wanyu /var/run/wanyu
sudo chown -R www-data:www-data /var/log/wanyu /var/run/wanyu
```

## 许可证

MIT License
