"""add is_vip and billing_exempt to Pouzivatel

Revision ID: e641ee96ccd5
Revises: a2b592fdc17b
Create Date: 2025-09-10 11:59:00.690973

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e641ee96ccd5'
down_revision = 'a2b592fdc17b'
branch_labels = None
depends_on = None


def upgrade():
    # SQLite potrebuje server_default pri NOT NULL nových stĺpcoch
    with op.batch_alter_table('pouzivatel', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_vip', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('billing_exempt', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    # voliteľne môžeš defaulty odstrániť (nie je nutné). Na SQLite to ale často vytvorí re-kópiu tabuľky,
    # takže ak chceš minimalizmus, tento blok môžeš vynechať.
    with op.batch_alter_table('pouzivatel', schema=None) as batch_op:
        batch_op.alter_column('is_vip', server_default=None)
        batch_op.alter_column('billing_exempt', server_default=None)


def downgrade():
    with op.batch_alter_table('pouzivatel', schema=None) as batch_op:
        batch_op.drop_column('billing_exempt')
        batch_op.drop_column('is_vip')


    # ### end Alembic commands ###
