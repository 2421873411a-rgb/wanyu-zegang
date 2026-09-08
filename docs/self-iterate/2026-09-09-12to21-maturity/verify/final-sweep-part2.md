== FINAL SWEEP part2 2026-09-09 02:26:03 ==
--- ruff ---
All checks passed!
EXIT=0
--- bash -n ×4 ---
deploy.sh OK
scripts/backup_database.sh OK
scripts/restore_drill.sh OK
scripts/upgrade_drill.sh OK
--- pytest full ---
101 passed, 5 skipped in 96.29s (0:01:36)
--- alembic roundtrip ---
ROUNDTRIP_EXIT=0
--- pip-audit ×2 ---
No known vulnerabilities found
requests.exceptions.ReadTimeout: HTTPSConnectionPool(host='pypi.org', port=443): Read timed out. (read timeout=15)
