"""user ratings MVP

Revision ID: 84e64a5fc80f
Revises: 5225307a69e8
Create Date: 2025-09-26 13:05:28.484189

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '84e64a5fc80f'
down_revision = '5225307a69e8'
branch_labels = None
depends_on = None


def upgrade():
    # (voliteľné – ak predchádzajúci neúspešný beh stihol vytvoriť tabuľku)
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if not insp.has_table('user_rating'):
        op.create_table(
            'user_rating',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('ratee_id', sa.Integer(), sa.ForeignKey('pouzivatel.id'), nullable=False, index=True),
            sa.Column('rater_id', sa.Integer(), sa.ForeignKey('pouzivatel.id'), nullable=False, index=True),
            sa.Column('recommend', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('stars', sa.Integer()),
            sa.Column('category_key', sa.String(length=40)),
            sa.Column('status', sa.String(length=12), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text("(datetime('now'))")),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text("(datetime('now'))")),
            sa.UniqueConstraint('ratee_id', 'rater_id', name='uq_rating_pair'),
        )

    with op.batch_alter_table('pouzivatel') as batch:
        batch.add_column(sa.Column('rating_count', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('rating_sum',   sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('rating_avg',   sa.Float(),   nullable=False, server_default='0'))
        batch.add_column(sa.Column('rating_bayes', sa.Float(),   nullable=False, server_default='0'))

    # (voliteľné) na ne-SQLite môžeš defaulty hneď odstrániť:
    # if conn.dialect.name != 'sqlite':
    #     with op.batch_alter_table('pouzivatel') as batch:
    #         batch.alter_column('rating_count', server_default=None)
    #         batch.alter_column('rating_sum',   server_default=None)
    #         batch.alter_column('rating_avg',   server_default=None)
    #         batch.alter_column('rating_bayes', server_default=None)

def downgrade():
    with op.batch_alter_table('pouzivatel') as batch:
        batch.drop_column('rating_bayes')
        batch.drop_column('rating_avg')
        batch.drop_column('rating_sum')
        batch.drop_column('rating_count')
    op.drop_table('user_rating')
