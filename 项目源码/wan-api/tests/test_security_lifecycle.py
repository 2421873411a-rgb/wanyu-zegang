"""v17.9.23 安全生命周期回归锁：dependabot 覆盖、weekly security-scan、SBOM 产物、轮换 runbook。"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WAN_API = Path(__file__).resolve().parents[1]


def test_dependabot_covers_pip_and_actions():
    text = (REPO / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert "package-ecosystem: pip" in text
    assert "package-ecosystem: github-actions" in text
    assert "interval: weekly" in text
    # 两个 pip 目录（API 与 canonical 工具链）都必须登记
    assert '"/项目源码/wan-api"' in text
    assert '"/项目源码"' in text


def test_weekly_security_scan_job_wired():
    wf = (REPO / ".github" / "workflows" / "wan-api-ci.yml").read_text(encoding="utf-8")
    assert "schedule:" in wf and "cron:" in wf
    assert "security-scan:" in wf
    # 仅 schedule/dispatch 触发，不进 PR 门禁（避免新增 required-check 期望）
    assert "github.event_name == 'schedule'" in wf
    # 审计不吞退出码 + SBOM 产物上传
    assert "--strict" in wf
    assert "cyclonedx-json" in wf
    assert "actions/upload-artifact" in wf
