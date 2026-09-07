"""0004 performance indexes + record_status backfill

Revision ID: f3a91c2d7e04
Revises: 8327a515dc2e
Create Date: 2026-09-08

- record_status 回填 + server_default（审计 A4：0002 对已 populated 库无回填，
  升级窗口内全表 NULL → 公共查询清空）
- 复合索引 (record_status, num DESC)：sort=recruits 曾每请求全量 TEMP B-TREE（371ms 实测）
- GIN trgm 索引（仅 PostgreSQL）：keyword ilike '%x%' 全表扫 168-294ms；
  pg_trgm 在 deploy.sh 已建扩展，此处建索引（SQLite 跳过）
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f3a91c2d7e04'
down_revision: Union[str, None] = '8327a515dc2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TRGM_COLUMNS = ('unit', 'zw', 'zy', 'code')


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == 'postgresql'

    op.execute("UPDATE jobs SET record_status='active' WHERE record_status IS NULL")
    if is_pg:
        op.alter_column('jobs', 'record_status', existing_type=sa.String(length=32),
                        server_default='active')
    else:
        # SQLite 不支持 ALTER COLUMN SET DEFAULT：batch 模式重建表落地列默认
        with op.batch_alter_table('jobs') as batch:
            batch.alter_column('record_status', existing_type=sa.String(length=32),
                               server_default='active')

    op.create_index('ix_jobs_record_status_num', 'jobs',
                    ['record_status', sa.text('num DESC')], unique=False)

    if is_pg:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        for col in _TRGM_COLUMNS:
            op.create_index(f'ix_jobs_{col}_trgm', 'jobs', [col],
                            postgresql_using='gin',
                            postgresql_ops={col: 'gin_trgm_ops'},
                            unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        for col in _TRGM_COLUMNS:
            op.drop_index(f'ix_jobs_{col}_trgm', table_name='jobs')
    op.drop_index('ix_jobs_record_status_num', table_name='jobs')
    if bind.dialect.name == 'postgresql':
        op.alter_column('jobs', 'record_status', existing_type=sa.String(length=32),
                        server_default=None)
    else:
        with op.batch_alter_table('jobs') as batch:
            batch.alter_column('record_status', existing_type=sa.String(length=32),
                               server_default=None)
