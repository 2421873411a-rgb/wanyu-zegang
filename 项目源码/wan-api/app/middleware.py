"""v17.10.0 请求上下文中间件：request-id 透传 + 结构化访问日志 + 进程内指标。

- request-id：优先透传调用方 X-Request-ID（便于网关串联），否则生成 16 位 hex；
  响应头回写 X-Request-ID。
- 访问日志：JSON 行（logging.getLogger("wanyu.access")），/health 不记（探活噪音）。
- 指标：methods/status/latency 直方图进 /metrics（METRICS_TOKEN 保护）。
"""
from __future__ import annotations

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability import metrics

access_logger = logging.getLogger("wanyu.access")

# /health 被探活高频轮询，访问日志不记（指标照常累计）
_ACCESS_LOG_EXCLUDED = {"/health"}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            metrics.observe(request.method, 500, duration_ms)
            metrics.record_error(type(exc).__name__)
            access_logger.exception(
                json.dumps({
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": 500,
                    "duration_ms": duration_ms,
                    "event": "unhandled_exception",
                    "exc_type": type(exc).__name__,
                }, ensure_ascii=False)
            )
            raise
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        metrics.observe(request.method, response.status_code, duration_ms)
        if request.url.path not in _ACCESS_LOG_EXCLUDED:
            access_logger.info(json.dumps({
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            }, ensure_ascii=False))
        return response
