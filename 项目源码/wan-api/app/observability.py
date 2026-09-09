"""v17.10.0 轻量可观测性：进程内计数 + Prometheus 文本渲染（零新依赖）。

多 worker 下各进程独立计数（本模块不做跨进程聚合）；/metrics 由 METRICS_TOKEN 保护，
未配置 token 时端点 404 隐藏存在。日志侧配套：wanyu.access（结构化访问日志）、
wanyu.db（慢查询），见 RUNBOOK「可观测性」。
"""
from __future__ import annotations

import threading
import time

_LATENCY_BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500)


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = time.time()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self.requests_total = 0
        self.requests_by_status = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
        self.requests_by_method: dict[str, int] = {}
        self.errors_by_type: dict[str, int] = {}
        self.latency_bucket_counts = [0] * len(_LATENCY_BUCKETS_MS)
        self.latency_count = 0
        self.latency_sum_ms = 0.0
        self.latency_max_ms = 0.0
        self.slow_queries = 0

    def observe_slow_query(self, duration_ms: float, statement: str) -> None:
        with self._lock:
            self.slow_queries += 1

    def reset(self) -> None:
        with self._lock:
            self._started_at = time.time()
            self._reset_locked()

    def observe(self, method: str, status_code: int, duration_ms: float) -> None:
        klass = f"{status_code // 100}xx"
        with self._lock:
            self.requests_total += 1
            if klass in self.requests_by_status:
                self.requests_by_status[klass] += 1
            self.requests_by_method[method] = self.requests_by_method.get(method, 0) + 1
            for index, bound in enumerate(_LATENCY_BUCKETS_MS):
                if duration_ms <= bound:
                    self.latency_bucket_counts[index] += 1
            self.latency_count += 1
            self.latency_sum_ms += duration_ms
            self.latency_max_ms = max(self.latency_max_ms, duration_ms)

    def record_error(self, exc_type: str) -> None:
        with self._lock:
            self.errors_by_type[exc_type] = self.errors_by_type.get(exc_type, 0) + 1

    def render(self) -> str:
        with self._lock:
            uptime = time.time() - self._started_at
            lines = [
                "# HELP wanyu_requests_total Total requests observed since process start.",
                "# TYPE wanyu_requests_total counter",
                f"wanyu_requests_total {self.requests_total}",
                "# HELP wanyu_requests_status_total Requests by status class.",
                "# TYPE wanyu_requests_status_total counter",
            ]
            for klass in ("2xx", "3xx", "4xx", "5xx"):
                lines.append(f'wanyu_requests_status_total{{class="{klass}"}} {self.requests_by_status[klass]}')
            lines += [
                "# HELP wanyu_requests_method_total Requests by HTTP method.",
                "# TYPE wanyu_requests_method_total counter",
            ]
            for method, count in sorted(self.requests_by_method.items()):
                lines.append(f'wanyu_requests_method_total{{method="{method}"}} {count}')
            lines += [
                "# HELP wanyu_request_duration_seconds Request latency in seconds.",
                "# TYPE wanyu_request_duration_seconds histogram",
            ]
            cumulative = 0
            for bound, count in zip(_LATENCY_BUCKETS_MS, self.latency_bucket_counts):
                cumulative += count
                lines.append(f'wanyu_request_duration_seconds_bucket{{le="{bound / 1000:g}"}} {cumulative}')
            lines.append('wanyu_request_duration_seconds_bucket{le="+Inf"} ' + str(self.latency_count))
            lines.append(f"wanyu_request_duration_seconds_sum {round(self.latency_sum_ms / 1000, 6)}")
            lines.append(f"wanyu_request_duration_seconds_count {self.latency_count}")
            lines += [
                "# HELP wanyu_errors_total Unhandled exceptions by exception type.",
                "# TYPE wanyu_errors_total counter",
            ]
            for exc_type, count in sorted(self.errors_by_type.items()):
                lines.append(f'wanyu_errors_total{{type="{exc_type}"}} {count}')
            lines += [
                "# HELP wanyu_uptime_seconds Process uptime in seconds.",
                "# TYPE wanyu_uptime_seconds gauge",
                f"wanyu_uptime_seconds {round(uptime, 1)}",
                "# HELP wanyu_slow_queries_total Slow queries logged since process start.",
                "# TYPE wanyu_slow_queries_total counter",
                f"wanyu_slow_queries_total {self.slow_queries}",
                "",
            ]
            return "\n".join(lines)


metrics = Metrics()
