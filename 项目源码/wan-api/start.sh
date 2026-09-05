#!/bin/bash
# 皖域择岗 API 启动脚本（开发环境）

set -e

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 设置环境变量
export APP_ENV=development
export DEBUG=true

# 启动FastAPI应用
echo "启动皖域择岗 API 开发服务器..."
echo "API文档: http://127.0.0.1:8000/api/docs"
echo "按 Ctrl+C 停止服务器"

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
