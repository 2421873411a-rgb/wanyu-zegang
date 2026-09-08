# 皖域择岗 API

> ⚠️ **EXPERIMENTAL / NOT FOR PRODUCTION**：wan-api 处于原型态，
> 安全与测试门禁见 `docs/CONTRACT.md`；满足上线前置前不得对公网开放。

> **v17.9.22 状态（2026-09-09）**：已通过 deploy.sh 全流程部署至生产 wan.kaogong.art（幂等导入、
> 迁移前后双快照、smoke 全过、公网验证），真机演练闭环：upgrade_drill 四不变量 ALL PASS、
> restore_drill PASS（checksum→pg_restore→revision/行数对账）、自动回滚 rollback_to_previous
> 实弹验证成功。**唯一未闭环项：COS 异地副本**（需站长腾讯云控制台配置 coscli 凭据与桶版本化，
> 当前备份仅为本机恢复点，整机故障不受保护）。证据：docs/self-iterate/2026-09-09-12to21-maturity/verify/prod-*.md


基于 FastAPI 的岗位数据与用户工作台后端。**当前正式站（静态）未接入本 API**——
线上收藏/对比为浏览器 localStorage，wan-api 为未来动态站预建（用户系统/搜索/管理导入/审计面）。

## 功能特性

- **用户系统**：注册/登录、JWT认证、收藏/快照云端同步
- **岗位搜索**：全文搜索、多维筛选、分页查询
- **数据管理**：后台管理界面、数据导入导出
- **API文档**：自动生成的Swagger/ReDoc文档

## 技术栈

- **后端框架**：FastAPI >=0.141.1
- **数据库**：PostgreSQL 16 + SQLAlchemy 2.0
- **限流后端**：memory（默认，单 worker）/ Redis（多 worker；Lua 原子滑动窗，生产默认）
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
├── tests/                # 门禁式测试套件（pytest；见 docs/CONTRACT.md §5）
├── scripts/              # 运维脚本（管理员、备份、restore/upgrade drill）
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

复制 `.env.example` 为 `.env` 并修改配置。**SECRET_KEY 必填**（v17.9.12 门禁：
缺失/公开默认值/弱密钥一律拒启）：

```bash
cp .env.example .env
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
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

仅在 `docs/CONTRACT.md` §7 的现场门禁完成后执行；仓库内测试通过不等于生产部署已验收。

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

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | Register |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/auth/refresh` | Refresh Token |
| POST | `/api/v1/auth/logout` | Logout |
| GET | `/api/v1/auth/me` | Get Me |

### 岗位

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/jobs/search` | Search Jobs |
| GET | `/api/v1/jobs/{record_id}` | Get Job |
| GET | `/api/v1/jobs/stats/by-city` | Get Jobs By City |
| GET | `/api/v1/jobs/stats/by-exam` | Get Jobs By Exam |

### 用户工作台

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/user/positions` | Get Saved Positions |
| POST | `/api/v1/user/positions` | Add Saved Position |
| DELETE | `/api/v1/user/positions/{record_id}` | Remove Saved Position |
| GET | `/api/v1/user/snapshots` | Get Snapshots |
| POST | `/api/v1/user/snapshots` | Create Snapshot |
| DELETE | `/api/v1/user/snapshots/{snapshot_id}` | Delete Snapshot |
| GET | `/api/v1/user/compare` | Get Compare List |
| POST | `/api/v1/user/compare` | Add To Compare |
| DELETE | `/api/v1/user/compare/{record_id}` | Remove From Compare |

### 周期

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/cycles` | Get Cycles |
| GET | `/api/v1/cycles/{cycle}` | Get Cycle |

### 待遇

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/salary` | Get Salary |
| GET | `/api/v1/salary/ranking` | Get Salary Ranking |

### 审计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/audit/review-queue` | Get Review Queue |

### 管理后台

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/dashboard` | Get Dashboard |
| GET | `/api/v1/admin/users` | Get Users |
| PUT | `/api/v1/admin/users/{user_id}` | Update User |
| POST | `/api/v1/admin/import/{cycle}` | Import Cycle Data |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Root |
| GET | `/health` | Health |

## 测试

> v17.9.19 起 tests/ 除 API/数据库门禁外，还会在临时目录执行真实运维 shell 行为（特权、
> PostgreSQL、systemd、COS 边界使用受控替身），覆盖：
> 注册不可成为管理员 / 生产 SECRET_KEY 拒绝启动 / refresh 仅 body + 轮换撤销 /
> 重复收藏数据库拒绝 / 对比≤4 / 管理导入真实写库对账 / 最后管理员保护 / 413 / 登出。
> 契约详见 `docs/CONTRACT.md`。

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_auth.py

# 运行带覆盖率的测试
# --cov 需先 pip install pytest-cov
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
sudo chown -R www-data:www-data /var/log/wanyu /var/run/wanyu
```

## 许可证

MIT License
