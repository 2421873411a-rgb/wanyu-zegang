...........................................................FF.FFFFsssss. [ 70%]
..............................                                           [100%]
================================== FAILURES ===================================
________ test_backup_copies_verifiable_checksums_to_weekly_and_monthly ________

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
    
>           assert result.returncode == 0, result.stdout + result.stderr
E           AssertionError: scripts/backup_database.sh: line 43: sudo: command not found
E             
E           assert 127 == 0
E            +  where 127 = CompletedProcess(args=['D:\\应用\\Git\\usr\\bin\\bash.EXE', '-c', '\nexport PATH="$(pwd)/tests/_ops-backup-sg9a54zc/bin:...up_database.sh\n'], returncode=127, stdout='', stderr='scripts/backup_database.sh: line 43: sudo: command not found\n').returncode

tests\test_ops_scripts.py:396: AssertionError
________ test_backup_uploads_dump_and_checksum_when_cos_is_configured _________

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
    
>           assert result.returncode == 0, result.stdout + result.stderr
E           AssertionError: scripts/backup_database.sh: line 43: sudo: command not found
E             
E           assert 127 == 0
E            +  where 127 = CompletedProcess(args=['D:\\应用\\Git\\usr\\bin\\bash.EXE', '-c', '\nexport PATH="$(pwd)/tests/_ops-cos-r4b12mpk/bin:$PA...up_database.sh\n'], returncode=127, stdout='', stderr='scripts/backup_database.sh: line 43: sudo: command not found\n').returncode

tests\test_ops_scripts.py:463: AssertionError
_ test_restore_creates_database_before_restore_and_uses_release_venv[success] _

active_count = '8401', fail_create = '0'
alembic_heads = 'f3a91c2d7e04 (head)\\n', expected_code = 0

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
    
>           assert result.returncode == expected_code, result.stdout + result.stderr
E           AssertionError: [drill] 备份文件：E:/zcode/择岗/项目源码/wan-api/tests/_ops-restore-hxv7q0k1/backup/daily/wanyu_db-20260908-030000.dump
E             wanyu_db-20260908-030000.dump: OK
E             [drill] sha256 校验 PASS
E             scripts/restore_drill.sh: line 22: sudo: command not found
E             
E           assert 127 == 0
E            +  where 127 = CompletedProcess(args=['D:\\应用\\Git\\usr\\bin\\bash.EXE', '-c', '\nexport PATH="$(pwd)/tests/_ops-restore-hxv7q0k1/bin...0908-030000.dump: OK\n[drill] sha256 校验 PASS\n', stderr='scripts/restore_drill.sh: line 22: sudo: command not found\n').returncode

tests\test_ops_scripts.py:610: AssertionError
_ test_restore_creates_database_before_restore_and_uses_release_venv[validation-failure-cleans-up] _

active_count = '0', fail_create = '0', alembic_heads = 'f3a91c2d7e04 (head)\\n'
expected_code = 1

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
    
>           assert result.returncode == expected_code, result.stdout + result.stderr
E           AssertionError: [drill] 备份文件：E:/zcode/择岗/项目源码/wan-api/tests/_ops-restore-waai2z62/backup/daily/wanyu_db-20260908-030000.dump
E             wanyu_db-20260908-030000.dump: OK
E             [drill] sha256 校验 PASS
E             scripts/restore_drill.sh: line 22: sudo: command not found
E             
E           assert 127 == 1
E            +  where 127 = CompletedProcess(args=['D:\\应用\\Git\\usr\\bin\\bash.EXE', '-c', '\nexport PATH="$(pwd)/tests/_ops-restore-waai2z62/bin...0908-030000.dump: OK\n[drill] sha256 校验 PASS\n', stderr='scripts/restore_drill.sh: line 22: sudo: command not found\n').returncode

tests\test_ops_scripts.py:610: AssertionError
_ test_restore_creates_database_before_restore_and_uses_release_venv[create-failure-cleans-up] _

active_count = '8401', fail_create = '1'
alembic_heads = 'f3a91c2d7e04 (head)\\n', expected_code = 43

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
    
>           assert result.returncode == expected_code, result.stdout + result.stderr
E           AssertionError: [drill] 备份文件：E:/zcode/择岗/项目源码/wan-api/tests/_ops-restore-y3duo5bb/backup/daily/wanyu_db-20260908-030000.dump
E             wanyu_db-20260908-030000.dump: OK
E             [drill] sha256 校验 PASS
E             scripts/restore_drill.sh: line 22: sudo: command not found
E             
E           assert 127 == 43
E            +  where 127 = CompletedProcess(args=['D:\\应用\\Git\\usr\\bin\\bash.EXE', '-c', '\nexport PATH="$(pwd)/tests/_ops-restore-y3duo5bb/bin...0908-030000.dump: OK\n[drill] sha256 校验 PASS\n', stderr='scripts/restore_drill.sh: line 22: sudo: command not found\n').returncode

tests\test_ops_scripts.py:610: AssertionError
_ test_restore_creates_database_before_restore_and_uses_release_venv[multiple-heads-fail-closed] _

active_count = '8401', fail_create = '0'
alembic_heads = 'f3a91c2d7e04 (head)\\nsecondhead000 (head)\\n'
expected_code = 1

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
    
>           assert result.returncode == expected_code, result.stdout + result.stderr
E           AssertionError: [drill] 备份文件：E:/zcode/择岗/项目源码/wan-api/tests/_ops-restore-oi_xou3p/backup/daily/wanyu_db-20260908-030000.dump
E             wanyu_db-20260908-030000.dump: OK
E             [drill] sha256 校验 PASS
E             scripts/restore_drill.sh: line 22: sudo: command not found
E             
E           assert 127 == 1
E            +  where 127 = CompletedProcess(args=['D:\\应用\\Git\\usr\\bin\\bash.EXE', '-c', '\nexport PATH="$(pwd)/tests/_ops-restore-oi_xou3p/bin...0908-030000.dump: OK\n[drill] sha256 校验 PASS\n', stderr='scripts/restore_drill.sh: line 22: sudo: command not found\n').returncode

tests\test_ops_scripts.py:610: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_ops_scripts.py::test_backup_copies_verifiable_checksums_to_weekly_and_monthly
FAILED tests/test_ops_scripts.py::test_backup_uploads_dump_and_checksum_when_cos_is_configured
FAILED tests/test_ops_scripts.py::test_restore_creates_database_before_restore_and_uses_release_venv[success]
FAILED tests/test_ops_scripts.py::test_restore_creates_database_before_restore_and_uses_release_venv[validation-failure-cleans-up]
FAILED tests/test_ops_scripts.py::test_restore_creates_database_before_restore_and_uses_release_venv[create-failure-cleans-up]
FAILED tests/test_ops_scripts.py::test_restore_creates_database_before_restore_and_uses_release_venv[multiple-heads-fail-closed]
6 failed, 91 passed, 5 skipped in 88.81s (0:01:28)
PYTEST_EXIT=1
