"""rychly_dopyt safe create"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ea17dc916906'          # ← z názvu súboru
down_revision = '29b4769ee7d4'      # ← tvoja baseline
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # vytvor tabuľku len ak ešte neexistuje
    if 'rychly_dopyt' not in set(insp.get_table_names()):
        op.create_table(
            'rychly_dopyt',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('text', sa.Text(), nullable=False),
            sa.Column('mesto_id', sa.Integer(), nullable=True),
            sa.Column('autor_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('plati_do', sa.DateTime(), nullable=False),
            sa.Column('aktivny', sa.Boolean(), nullable=False),
            sa.Column('archived_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['mesto_id'], ['mesto.id']),
            sa.ForeignKeyConstraint(['autor_id'], ['pouzivatel.id']),
            sa.PrimaryKeyConstraint('id')
        )

    # doplň indexy len ak chýbajú
    try:
        existing = {ix['name'] for ix in insp.get_indexes('rychly_dopyt')}
    except Exception:
        existing = set()

    def ensure_ix(name, cols):
        if name not in existing:
            op.create_index(name, 'rychly_dopyt', cols, unique=False)

    ensure_ix('ix_rychly_dopyt_aktivny',    ['aktivny'])
    ensure_ix('ix_rychly_dopyt_autor_id',   ['autor_id'])
    ensure_ix('ix_rychly_dopyt_created_at', ['created_at'])
    ensure_ix('ix_rychly_dopyt_mesto_id',   ['mesto_id'])
    ensure_ix('ix_rychly_dopyt_plati_do',   ['plati_do'])


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        op.execute(sa.text('DROP INDEX IF EXISTS ix_rychly_dopyt_plati_do'))
        op.execute(sa.text('DROP INDEX IF EXISTS ix_rychly_dopyt_mesto_id'))
        op.execute(sa.text('DROP INDEX IF EXISTS ix_rychly_dopyt_created_at'))
        op.execute(sa.text('DROP INDEX IF EXISTS ix_rychly_dopyt_autor_id'))
        op.execute(sa.text('DROP INDEX IF EXISTS ix_rychly_dopyt_aktivny'))
        op.execute(sa.text('DROP TABLE IF EXISTS rychly_dopyt'))
    else:
        insp = sa.inspect(bind)
        if 'rychly_dopyt' in set(insp.get_table_names()):
            for name in ['ix_rychly_dopyt_plati_do','ix_rychly_dopyt_mesto_id',
                         'ix_rychly_dopyt_created_at','ix_rychly_dopyt_autor_id',
                         'ix_rychly_dopyt_aktivny']:
                op.drop_index(name, table_name='rychly_dopyt')
            op.drop_table('rychly_dopyt')
