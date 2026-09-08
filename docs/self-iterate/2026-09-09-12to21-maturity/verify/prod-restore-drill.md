== 手动备份（新权限逻辑）==
LOCAL RECOVERY POINT ONLY: COS_BUCKET 未配置；整机故障不受保护
backup ok: /opt/wanyu/backup/daily/wanyu_db-20260909-073639.dump
latest: 
== restore_drill ==
[drill] sha256 校验 PASS
NOTICE:  database "wanyu_restore_drill" does not exist, skipping
[drill] pg_restore PASS
[drill] alembic revision PASS (f3a91c2d7e04)
[drill] jobs 2024 = 10017
[drill] jobs 2025 = 10150
[drill] jobs 2026 = 8511
[drill] salary=160 review=7 users=3
[DRILL PASS] dump 可恢复、schema 与 canonical 基线正确（退出时清理临时库）
[drill] 临时库已清理：wanyu_restore_drill
