"""rename vztah mesto -> mesto_ref + timestamps

Revision ID: e142949b943a
Revises: d4fe0b0a1870
Create Date: 2025-08-26 14:36:41.366074

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e142949b943a'
down_revision = 'd4fe0b0a1870'
branch_labels = None
depends_on = None

def upgrade():
    # SQLite potrebuje server_default pri NOT NULL stĺpcoch
    with op.batch_alter_table('dopyt', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'created_at',
                sa.DateTime(),
                nullable=False,
                server_default=sa.text('CURRENT_TIMESTAMP')
            )
        )
        batch_op.add_column(
            sa.Column(
                'updated_at',
                sa.DateTime(),
                nullable=False,
                server_default=sa.text('CURRENT_TIMESTAMP')
            )
        )

    # (voliteľné) server_default môžeš hneď zrušiť, ak chceš nech to riadi app layer
    with op.batch_alter_table('dopyt', schema=None) as batch_op:
        batch_op.alter_column('created_at', server_default=None)
        batch_op.alter_column('updated_at', server_default=None)


def downgrade():
    with op.batch_alter_table('dopyt', schema=None) as batch_op:
        batch_op.drop_column('updated_at')
        batch_op.drop_column('created_at')

