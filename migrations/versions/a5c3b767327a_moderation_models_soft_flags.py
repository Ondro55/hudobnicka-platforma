"""moderation models + soft flags

Revision ID: a5c3b767327a
Revises: e142949b943a
Create Date: 2025-08-27 08:59:05.674771

"""
from alembic import op
import sqlalchemy as sa

revision = 'a5c3b767327a'
down_revision = 'e142949b943a'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c['name'] for c in insp.get_columns('pouzivatel')}

    if 'is_admin' not in cols:
        op.execute("ALTER TABLE pouzivatel ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    if 'is_moderator' not in cols:
        op.execute("ALTER TABLE pouzivatel ADD COLUMN is_moderator INTEGER NOT NULL DEFAULT 0")
    if 'strikes_count' not in cols:
        op.execute("ALTER TABLE pouzivatel ADD COLUMN strikes_count INTEGER NOT NULL DEFAULT 0")
    if 'banned_until' not in cols:
        op.execute("ALTER TABLE pouzivatel ADD COLUMN banned_until DATETIME")
    if 'banned_reason' not in cols:
        op.execute("ALTER TABLE pouzivatel ADD COLUMN banned_reason VARCHAR(255)")

def downgrade():
    # SQLite DROP COLUMN nepodporuje – nechávame prázdne
    pass


