"""Production-ops shell scripts: executable behavior regressions.

These tests run the real Bash functions/scripts while replacing only privileged
or external boundaries such as sudo, PostgreSQL, systemd, and COS.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest


WAN_API = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="bash is required for ops script tests")


def run_bash(script: str, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [BASH, "-c", script],
        cwd=WAN_API,
        env=merged_env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def test_deploy_script_can_be_sourced_without_running_main():
    """Sourcing function definitions must not start a privileged deployment."""
    result = run_bash("source ./deploy.sh; printf sourced")

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.endswith("sourced")


def test_sourced_deploy_resolves_metadata_from_its_own_file():
    """A sourced deploy script must not derive paths from the caller's $0."""
    deploy_path = (WAN_API / "deploy.sh").as_posix()
    result = run_bash(f'cd /; source "{deploy_path}"; printf "%s" "$RELEASE_JSON"')

    assert result.returncode == 0, result.stdout + result.stderr
    expected = (WAN_API / "release.json").resolve().as_posix()
    if len(expected) >= 3 and expected[1:3] == ":/":
        expected = "/" + expected[0].lower() + expected[2:]
    assert result.stdout == expected


def test_main_loads_release_before_secret_setup():
    """The secret writer must observe release.json, never the empty bootstrap value."""
    result = run_bash(
        r'''
source ./deploy.sh
RELEASE_JSON="./release.json"
APP_VERSION="sentinel-stale"
RELEASE_DIR="/tmp/test-release"
observed=""
python3() { printf 'v17.9.19\n'; }
check_root() { :; }
check_prerequisites() { :; }
install_dependencies() { :; }
setup_database() { :; }
setup_secret_env() { observed="$APP_VERSION"; }
build_release() { :; }
setup_service() { :; }
setup_logrotate() { :; }
setup_backup_automation() { :; }
setup_nginx() { :; }
setup_ssl() { :; }
stop_service_window() { :; }
atomic_switch() { :; }
import_data() { :; }
start_service() { :; }
post_deploy_smoke() { :; }
bootstrap_admin() { :; }
prune_old_releases() { :; }
main
printf 'OBSERVED=%s' "$observed"
'''
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.endswith("OBSERVED=v17.9.19"), result.stdout


def test_import_guard_requires_all_three_cycle_results():
    """The deployment guard must reject a partial import, not only an empty one."""
    script = (WAN_API / "deploy.sh").read_text(encoding="utf-8")

    assert "if not all(cycles):" in script


def test_run_as_app_loads_the_external_secret_environment():
    """Privileged migration/import CLIs must receive the same EnvironmentFile as systemd."""
    with tempfile.TemporaryDirectory(prefix="_ops-env-", dir=WAN_API / "tests") as temp_name:
        temp_root = Path(temp_name)
        secret_env = temp_root / "wanyu.env"
        secret_env.write_text(
            "APP_VERSION=v17.9.19\n"
            "DATABASE_URL=postgresql+asyncpg://fixture/db\n"
            "SECRET_KEY=fixture-secret-key-0123456789abcdef\n"
            "CORS_ORIGINS='[\"https://wan.kaogong.art\"]'\n",
            encoding="utf-8",
            newline="\n",
        )
        env_rel = secret_env.relative_to(WAN_API).as_posix()
        result = run_bash(
            rf'''
source ./deploy.sh
SECRET_ENV="$(pwd)/{env_rel}"
python3() {{ python "$@"; }}
sudo() {{
    if [ "${{1:-}}" = "-u" ]; then shift 2; fi
    "$@"
}}
run_as_app python -c 'import os; print("|".join(os.environ[name] for name in ("APP_VERSION", "DATABASE_URL", "CORS_ORIGINS")), end="")'
'''
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.endswith(
            'v17.9.19|postgresql+asyncpg://fixture/db|["https://wan.kaogong.art"]'
        ), result.stdout


def test_migration_and_import_commands_use_the_environment_runner():
    """Both release CLIs must cross the tested EnvironmentFile boundary."""
    with tempfile.TemporaryDirectory(prefix="_ops-import-", dir=WAN_API / "tests") as temp_name:
        release = Path(temp_name) / "release"
        call_log = Path(temp_name) / "calls.log"
        (release / "app").mkdir(parents=True)
        release_rel = release.relative_to(WAN_API).as_posix()
        call_log_rel = call_log.relative_to(WAN_API).as_posix()
        result = run_bash(
            rf'''
source ./deploy.sh
RELEASE_DIR="$(pwd)/{release_rel}"
CALL_LOG="$(pwd)/{call_log_rel}"
run_as_app() {{
    printf '%s %s %s\n' "$1" "${{2:-}}" "${{3:-}}" >> "$CALL_LOG"
    if [[ "$1" == */python ]]; then
        cat > /dev/null
    fi
}}
migrate_and_import_release
'''
        )

        assert result.returncode == 0, result.stdout + result.stderr
        calls = call_log.read_text(encoding="utf-8").splitlines()
        assert calls[0].endswith("/venv/bin/alembic upgrade head"), calls
        assert calls[1].endswith("/venv/bin/python - "), calls


def test_admin_bootstrap_uses_the_environment_runner():
    """The admin CLI must not bypass the external production EnvironmentFile."""
    with tempfile.TemporaryDirectory(prefix="_ops-admin-", dir=WAN_API / "tests") as temp_name:
        current = Path(temp_name) / "current"
        call_log = Path(temp_name) / "calls.log"
        (current / "app").mkdir(parents=True)
        current_rel = current.relative_to(WAN_API).as_posix()
        call_log_rel = call_log.relative_to(WAN_API).as_posix()
        result = run_bash(
            rf'''
source ./deploy.sh
CURRENT_LINK="$(pwd)/{current_rel}"
CALL_LOG="$(pwd)/{call_log_rel}"
ADMIN_BOOTSTRAP_PASSWORD="fixture-password"
ADMIN_EMAIL="admin@example.test"
sudo() {{ :; }}
run_as_app() {{ printf '%s\n' "$*" >> "$CALL_LOG"; }}
bootstrap_admin
'''
        )

        assert result.returncode == 0, result.stdout + result.stderr
        call = call_log.read_text(encoding="utf-8")
        assert "/venv/bin/python scripts/create_admin.py" in call
        assert "--email admin@example.test" in call
        assert "--password fixture-password" in call


def test_import_data_snapshots_are_atomic_checksummed_and_revision_anchored():
    """Migration recovery evidence belongs beside the dump, without legacy LATEST paths."""
    with tempfile.TemporaryDirectory(prefix="_ops-snapshot-", dir=WAN_API / "tests") as temp_name:
        backup_root = Path(temp_name) / "backup"
        backup_rel = backup_root.relative_to(WAN_API).as_posix()
        result = run_bash(
            rf'''
source ./deploy.sh
BACKUP_ROOT="$(pwd)/{backup_rel}"
date() {{ printf '20260908-040000\n'; }}
sudo() {{
    if [ "${{1:-}}" = "-u" ]; then shift 2; fi
    case "${{1:-}}" in
        pg_dump) printf 'postgres-custom-format-fixture\n' ;;
        psql)
            if [[ " $* " == *to_regclass* ]]; then
                printf 'alembic_version\n'
            else
                printf 'f3a91c2d7e04\n'
            fi
            ;;
        *) "$@" ;;
    esac
}}
migrate_and_import_release() {{ :; }}
import_data
'''
        )

        assert result.returncode == 0, result.stdout + result.stderr
        pre_dump = backup_root / "wanyu_db-20260908-040000.dump"
        post_dump = backup_root / "wanyu_db-post-import-20260908-040000.dump"
        for dump in (pre_dump, post_dump):
            assert dump.is_file()
            assert Path(f"{dump}.sha256").is_file()
            backup_dir_rel = backup_root.relative_to(WAN_API).as_posix()
            verified = run_bash(
                f'cd "{backup_dir_rel}" && sha256sum -c "{dump.name}.sha256"'
            )
            assert verified.returncode == 0, verified.stdout + verified.stderr
        revision_file = Path(f"{pre_dump}.alembic-before.txt")
        assert revision_file.read_text(encoding="utf-8").strip() == "f3a91c2d7e04"


def test_build_only_delegates_to_build_release_once():
    """The drill CLI must call the production builder instead of a copied implementation."""
    result = run_bash(
        r'''
source ./deploy.sh
calls=0
RELEASE_DIR="/tmp/mock-release"
check_root() { :; }
load_release_metadata() { APP_VERSION="v17.9.19"; }
build_release() { calls=$((calls + 1)); }
build_only_main
printf 'CALLS=%s SUFFIX=%s' "$calls" "${WANYU_RELEASE_SUFFIX:-}"
'''
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.endswith("CALLS=1 SUFFIX=-drill"), result.stdout


def test_shared_build_release_excludes_development_payload():
    """The one production builder must omit every development-only payload class."""
    with tempfile.TemporaryDirectory(prefix="_ops-build-", dir=WAN_API / "tests") as temp_name:
        temp_root = Path(temp_name)
        payload = temp_root / "payload"
        releases = temp_root / "releases"
        (payload / "app").mkdir(parents=True)
        (payload / "tests").mkdir()
        (payload / "docs").mkdir()
        (payload / "app" / "keep.py").write_text("KEEP = True\n", encoding="utf-8")
        (payload / "tests" / "leak.py").write_text("LEAK = True\n", encoding="utf-8")
        (payload / "docs" / "leak.md").write_text("leak\n", encoding="utf-8")
        (payload / "local.db").write_bytes(b"db")
        (payload / "_audit_probe_secret").write_text("probe\n", encoding="utf-8")
        (payload / "requirements.lock.txt").write_text("", encoding="utf-8")

        payload_rel = payload.relative_to(WAN_API).as_posix()
        releases_rel = releases.relative_to(WAN_API).as_posix()
        result = run_bash(
            rf'''
source ./deploy.sh
SCRIPT_DIR="$(pwd)/{payload_rel}"
RELEASES_DIR="$(pwd)/{releases_rel}"
APP_VERSION="v17.9.19"
WANYU_RELEASE_SUFFIX="-drill"
sudo() {{
    case "${{1:-}}" in
        chown) return 0 ;;
        find) shift; /usr/bin/find "$@" ;;
        *) "$@" ;;
    esac
}}
python3.12() {{
    local target="${{3:?venv target required}}"
    mkdir -p "$target/bin"
    printf '#!/bin/bash\nexit 0\n' > "$target/bin/pip"
    chmod +x "$target/bin/pip"
}}
git() {{ printf 'abc1234\n'; }}
build_release
'''
        )

        assert result.returncode == 0, result.stdout + result.stderr
        app_dir = releases / "v17.9.19-abc1234-drill" / "app"
        assert (app_dir / "app" / "keep.py").is_file()
        assert not (app_dir / "tests").exists()
        assert not (app_dir / "docs").exists()
        assert not (app_dir / "local.db").exists()
        assert not (app_dir / "_audit_probe_secret").exists()


def test_public_root_smoke_accepts_template_redirect_and_requires_final_200():
    """The fresh-host 302 root contract passes only when its target resolves to 200."""
    result = run_bash(
        r'''
source ./deploy.sh
curl() {
    if [[ " $* " == *L* ]]; then
        printf '200'
    else
        printf '302'
    fi
}
smoke_public_root
printf 'ROOT_SMOKE=PASS'
'''
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.endswith("ROOT_SMOKE=PASS"), result.stdout


def test_public_root_smoke_rejects_broken_redirect_target():
    """A redirect alone is insufficient when the final static page is not 200."""
    result = run_bash(
        r'''
source ./deploy.sh
curl() { printf '404'; }
if smoke_public_root; then
    exit 9
fi
printf 'ROOT_SMOKE=REJECTED'
'''
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.endswith("ROOT_SMOKE=REJECTED"), result.stdout


def test_backup_copies_verifiable_checksums_to_weekly_and_monthly():
    """A Sunday/month-start snapshot must keep a valid sidecar in every tier."""
    with tempfile.TemporaryDirectory(prefix="_ops-backup-", dir=WAN_API / "tests") as temp_name:
        temp_root = Path(temp_name)
        fake_bin = temp_root / "bin"
        backup_root = temp_root / "backup"
        fake_bin.mkdir()
        write_executable(
            fake_bin / "date",
            """#!/bin/bash
case "${1:-}" in
    +%Y%m%d-%H%M%S) printf '20260908-030000\\n' ;;
    +%u) printf '7\\n' ;;
    +%d) printf '01\\n' ;;
    *) exit 2 ;;
esac
""",
        )
        write_executable(
            fake_bin / "sudo",
            """#!/bin/bash
if [ "${1:-}" = "-u" ]; then shift 2; fi
exec "$@"
""",
        )
        write_executable(
            fake_bin / "pg_dump",
            """#!/bin/bash
printf 'postgres-custom-format-fixture\\n'
""",
        )

        fake_bin_rel = fake_bin.relative_to(WAN_API).as_posix()
        backup_rel = backup_root.relative_to(WAN_API).as_posix()
        result = run_bash(
            rf'''
export PATH="$(pwd)/{fake_bin_rel}:$PATH"
export WANYU_BACKUP_BASE="$(pwd)/{backup_rel}"
unset COS_BUCKET
bash scripts/backup_database.sh
'''
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert "LOCAL RECOVERY POINT ONLY" in result.stdout
        dump_name = "wanyu_db-20260908-030000.dump"
        for tier in ("daily", "weekly", "monthly"):
            tier_dir = backup_root / tier
            assert (tier_dir / dump_name).is_file()
            assert (tier_dir / f"{dump_name}.sha256").is_file()
            tier_rel = tier_dir.relative_to(WAN_API).as_posix()
            verified = run_bash(
                f'cd "{tier_rel}" && sha256sum -c "{dump_name}.sha256"'
            )
            assert verified.returncode == 0, verified.stdout + verified.stderr


def test_backup_uploads_dump_and_checksum_when_cos_is_configured():
    """Configured off-site backup must upload the data and its integrity proof."""
    with tempfile.TemporaryDirectory(prefix="_ops-cos-", dir=WAN_API / "tests") as temp_name:
        temp_root = Path(temp_name)
        fake_bin = temp_root / "bin"
        backup_root = temp_root / "backup"
        cos_log = temp_root / "cos.log"
        fake_bin.mkdir()
        write_executable(
            fake_bin / "date",
            """#!/bin/bash
case "${1:-}" in
    +%Y%m%d-%H%M%S) printf '20260908-030000\\n' ;;
    +%u) printf '1\\n' ;;
    +%d) printf '08\\n' ;;
    *) exit 2 ;;
esac
""",
        )
        write_executable(
            fake_bin / "sudo",
            """#!/bin/bash
if [ "${1:-}" = "-u" ]; then shift 2; fi
exec "$@"
""",
        )
        write_executable(
            fake_bin / "pg_dump",
            """#!/bin/bash
printf 'postgres-custom-format-fixture\\n'
""",
        )
        write_executable(
            fake_bin / "coscli",
            """#!/bin/bash
printf '%s\\n' "$*" >> "$COS_LOG"
""",
        )

        fake_bin_rel = fake_bin.relative_to(WAN_API).as_posix()
        backup_rel = backup_root.relative_to(WAN_API).as_posix()
        cos_log_rel = cos_log.relative_to(WAN_API).as_posix()
        result = run_bash(
            rf'''
export PATH="$(pwd)/{fake_bin_rel}:$PATH"
export WANYU_BACKUP_BASE="$(pwd)/{backup_rel}"
export COS_LOG="$(pwd)/{cos_log_rel}"
export COS_BUCKET="fixture-bucket"
export COSCLI="coscli"
bash scripts/backup_database.sh
'''
        )

        assert result.returncode == 0, result.stdout + result.stderr
        calls = cos_log.read_text(encoding="utf-8").splitlines()
        assert len(calls) == 2, calls
        assert calls[0].endswith(
            "cos://fixture-bucket/wanyu-db/daily/wanyu_db-20260908-030000.dump"
        )
        assert calls[1].endswith(
            "cos://fixture-bucket/wanyu-db/daily/wanyu_db-20260908-030000.dump.sha256"
        )


def test_deploy_installs_the_repository_backup_script():
    """The timer must execute the tested script, not a second heredoc implementation."""
    result = run_bash(
        r'''
source ./deploy.sh
SCRIPT_DIR="$(pwd)"
installed_source=""
installed_target=""
sudo() {
    case "${1:-}" in
        install)
            installed_source="$4"
            installed_target="$5"
            ;;
        tee)
            cat > /dev/null
            ;;
        *)
            :
            ;;
    esac
}
setup_backup_automation
printf 'SOURCE=%s TARGET=%s' "$installed_source" "$installed_target"
'''
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.endswith(
        "/scripts/backup_database.sh TARGET=/etc/wanyu/wanyu-backup.sh"
    ), result.stdout


@pytest.mark.parametrize(
    ("active_count", "fail_create", "alembic_heads", "expected_code"),
    [
        ("8401", "0", "f3a91c2d7e04 (head)\\n", 0),
        ("0", "0", "f3a91c2d7e04 (head)\\n", 1),
        ("8401", "1", "f3a91c2d7e04 (head)\\n", 43),
        ("8401", "0", "f3a91c2d7e04 (head)\\nsecondhead000 (head)\\n", 1),
    ],
    ids=[
        "success",
        "validation-failure-cleans-up",
        "create-failure-cleans-up",
        "multiple-heads-fail-closed",
    ],
)
def test_restore_creates_database_before_restore_and_uses_release_venv(
    active_count: str, fail_create: str, alembic_heads: str, expected_code: int
):
    """Restore must create its target first and resolve Alembic beside app/, not inside it."""
    with tempfile.TemporaryDirectory(prefix="_ops-restore-", dir=WAN_API / "tests") as temp_name:
        temp_root = Path(temp_name)
        fake_bin = temp_root / "bin"
        backup_daily = temp_root / "backup" / "daily"
        current = temp_root / "current"
        ops_log = temp_root / "ops.log"
        db_marker = temp_root / "db-created"
        fake_bin.mkdir()
        backup_daily.mkdir(parents=True)
        (current / "app").mkdir(parents=True)
        (current / "venv" / "bin").mkdir(parents=True)

        dump_name = "wanyu_db-20260908-030000.dump"
        dump = backup_daily / dump_name
        dump.write_bytes(b"postgres-custom-format-fixture\n")
        digest = hashlib.sha256(dump.read_bytes()).hexdigest()
        (backup_daily / f"{dump_name}.sha256").write_text(
            f"{digest}  {dump_name}\n", encoding="utf-8", newline="\n"
        )

        write_executable(
            fake_bin / "sudo",
            """#!/bin/bash
if [ "${1:-}" = "-u" ]; then shift 2; fi
exec "$@"
""",
        )
        write_executable(
            fake_bin / "psql",
            r'''#!/bin/bash
printf 'PSQL %s\n' "$*" >> "$OPS_LOG"
args="$*"
case "$args" in
    *"DROP DATABASE"*) rm -f "$DB_MARKER" ;;
    *"CREATE DATABASE"*)
        if [ "$FAIL_CREATE" = "1" ]; then exit 43; fi
        : > "$DB_MARKER"
        ;;
    *"SELECT version_num FROM alembic_version"*) printf 'f3a91c2d7e04\n' ;;
    *"cycle='2024'"*) printf '10017\n' ;;
    *"cycle='2025'"*) printf '10150\n' ;;
    *"cycle='2026'"*"record_status='active'"*) printf '%s\n' "$ACTIVE_COUNT" ;;
    *"cycle='2026'"*) printf '8511\n' ;;
    *"FROM salary_data"*) printf '160\n' ;;
    *"FROM review_events"*) printf '8\n' ;;
    *"FROM users"*) printf '1\n' ;;
esac
''',
        )
        write_executable(
            fake_bin / "pg_restore",
            r'''#!/bin/bash
printf 'RESTORE %s\n' "$*" >> "$OPS_LOG"
[ -f "$DB_MARKER" ] || { echo 'database was not created' >&2; exit 42; }
''',
        )
        write_executable(
            current / "venv" / "bin" / "alembic",
            r'''#!/bin/bash
printf 'ALEMBIC %s\n' "$*" >> "$OPS_LOG"
printf '%b' "$ALEMBIC_HEADS"
''',
        )

        fake_bin_rel = fake_bin.relative_to(WAN_API).as_posix()
        backup_rel = (temp_root / "backup").relative_to(WAN_API).as_posix()
        current_rel = current.relative_to(WAN_API).as_posix()
        log_rel = ops_log.relative_to(WAN_API).as_posix()
        marker_rel = db_marker.relative_to(WAN_API).as_posix()
        result = run_bash(
            rf'''
export PATH="$(pwd)/{fake_bin_rel}:$PATH"
export WANYU_BACKUP_BASE="$(pwd)/{backup_rel}"
export WANYU_CURRENT_LINK="$(pwd)/{current_rel}"
export WANYU_RESTORE_DRILL_DB="wanyu_restore_drill"
export OPS_LOG="$(pwd)/{log_rel}"
export DB_MARKER="$(pwd)/{marker_rel}"
export ACTIVE_COUNT="{active_count}"
export FAIL_CREATE="{fail_create}"
export ALEMBIC_HEADS="{alembic_heads}"
bash scripts/restore_drill.sh
'''
        )

        assert result.returncode == expected_code, result.stdout + result.stderr
        events = ops_log.read_text(encoding="utf-8").splitlines()
        create_index = next(i for i, line in enumerate(events) if "CREATE DATABASE" in line)
        if fail_create == "0":
            restore_index = next(i for i, line in enumerate(events) if line.startswith("RESTORE "))
            assert create_index < restore_index, events
            assert any(line == "ALEMBIC heads" for line in events), events
        else:
            assert not any(line.startswith("RESTORE ") for line in events), events
        assert "DROP DATABASE" in events[-1], events
        assert not db_marker.exists()
