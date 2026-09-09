"""v17.10.0 可观测性回归锁：request-id、结构化访问日志、/metrics 保护、慢查询日志。"""
import json
import logging

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.observability import metrics


@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


@pytest.mark.asyncio
async def test_request_id_generated_and_echoed(client):
    resp = await client.get("/health")
    assert resp.headers.get("x-request-id")
    resp2 = await client.get("/health", headers={"X-Request-ID": "e2e-trace-0001"})
    assert resp2.headers["x-request-id"] == "e2e-trace-0001"


@pytest.mark.asyncio
async def test_access_log_json_with_request_id(client, caplog):
    with caplog.at_level(logging.INFO, logger="wanyu.access"):
        await client.get("/health", headers={"X-Request-ID": "log-probe-0001"})
    records = [r for r in caplog.records if r.name == "wanyu.access"]
    # /health 在访问日志排除名单（探活噪音）——用真实业务路径验证
    with caplog.at_level(logging.INFO, logger="wanyu.access"):
        resp = await client.get("/api/v1/cycles", headers={"X-Request-ID": "log-probe-0002"})
    assert resp.status_code < 500
    records = [r for r in caplog.records if r.name == "wanyu.access"]
    assert records, "业务请求应产生访问日志"
    payload = json.loads(records[-1].getMessage())
    assert payload["request_id"] == "log-probe-0002"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v1/cycles"
    assert isinstance(payload["status"], int)
    assert isinstance(payload["duration_ms"], (int, float))


@pytest.mark.asyncio
async def test_metrics_hidden_without_token(client, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_TOKEN", "")
    resp = await client.get("/metrics")
    assert resp.status_code == 404
    resp = await client.get("/metrics", headers={"Authorization": "Bearer anything"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_metrics_with_token_exposes_counters(client, monkeypatch):
    monkeypatch.setattr(settings, "METRICS_TOKEN", "unit-metrics-token")
    await client.get("/health", headers={"X-Request-ID": "metrics-probe"})
    wrong = await client.get("/metrics", headers={"Authorization": "Bearer wrong"})
    assert wrong.status_code == 404
    resp = await client.get("/metrics", headers={"Authorization": "Bearer unit-metrics-token"})
    assert resp.status_code == 200
    body = resp.text
    assert resp.headers["content-type"].startswith("text/plain")
    assert "wanyu_requests_total " in body
    assert 'wanyu_requests_status_total{class="2xx"}' in body
    assert 'wanyu_request_duration_seconds_bucket{le="0.1"}' in body
    assert "wanyu_uptime_seconds" in body


@pytest.mark.asyncio
async def test_slow_query_logged_when_threshold_exceeded(monkeypatch, caplog):
    # 生产挂载点 = app.database.engine 的 before/after_cursor_execute 对；
    # 此处用满足 conn.info 协议的最小桩直呼监听器，确定性验证行为。
    import time as time_mod
    from app import database as app_database

    class _FakeConn:
        info = {}

    conn = _FakeConn()
    monkeypatch.setattr(settings, "SLOW_QUERY_MS", 1)
    app_database._before_cursor_execute(conn, None, "SELECT 1", None, None, False)
    time_mod.sleep(0.01)
    with caplog.at_level(logging.WARNING, logger="wanyu.db"):
        app_database._after_cursor_execute(conn, None, "SELECT 1", None, None, False)
    slow_records = [r for r in caplog.records if r.name == "wanyu.db"]
    assert slow_records, "超过阈值的查询必须记慢查询日志"
    payload = json.loads(slow_records[0].getMessage())
    assert payload["event"] == "slow_query"
    assert payload["statement"] == "SELECT 1"
    assert payload["duration_ms"] >= 1
    assert "wanyu_slow_queries_total 1" in metrics.render()


@pytest.mark.asyncio
async def test_slow_query_silent_below_threshold(monkeypatch, caplog):
    from app import database as app_database

    class _FakeConn:
        info = {}

    conn = _FakeConn()
    monkeypatch.setattr(settings, "SLOW_QUERY_MS", 60_000)
    app_database._before_cursor_execute(conn, None, "SELECT 1", None, None, False)
    with caplog.at_level(logging.WARNING, logger="wanyu.db"):
        app_database._after_cursor_execute(conn, None, "SELECT 1", None, None, False)
    assert not [r for r in caplog.records if r.name == "wanyu.db"]
