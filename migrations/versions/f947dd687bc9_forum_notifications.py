"""forum notifications

Revision ID: f947dd687bc9
Revises: ea17dc916906
Create Date: 2025-09-08 11:21:03.841039
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f947dd687bc9'
down_revision = 'ea17dc916906'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # --- forum_notification: create only if missing ---
    existing_tables = set(insp.get_table_names())
    if 'forum_notification' not in existing_tables:
        op.create_table(
            'forum_notification',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('topic_id', sa.Integer(), nullable=False),
            sa.Column('post_id', sa.Integer(), nullable=False),
            sa.Column('reason', sa.String(length=32), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('read_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['pouzivatel.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'post_id', name='uq_forumnotif_user_post'),
        )
        op.create_index('ix_forum_notification_post_id', 'forum_notification', ['post_id'], unique=False)
        op.create_index('ix_forum_notification_topic_id', 'forum_notification', ['topic_id'], unique=False)
        op.create_index('ix_forum_notification_user_id', 'forum_notification', ['user_id'], unique=False)
    else:
        # doplň prípadne chýbajúce indexy (bez padania, ak už sú)
        try:
            existing_indexes = {ix['name'] for ix in insp.get_indexes('forum_notification')}
        except Exception:
            existing_indexes = set()
        if 'ix_forum_notification_post_id' not in existing_indexes:
            op.create_index('ix_forum_notification_post_id', 'forum_notification', ['post_id'], unique=False)
        if 'ix_forum_notification_topic_id' not in existing_indexes:
            op.create_index('ix_forum_notification_topic_id', 'forum_notification', ['topic_id'], unique=False)
        if 'ix_forum_notification_user_id' not in existing_indexes:
            op.create_index('ix_forum_notification_user_id', 'forum_notification', ['user_id'], unique=False)
        # unikát na (user_id, post_id) – ak nemá náš pomenovaný constraint, ale už je tam iný,
        # nenecháme padnúť. Kontrola podľa stĺpcov:
        try:
            uqs = insp.get_unique_constraints('forum_notification')
            has_user_post_unique = any(set(uc.get('column_names', [])) == {'user_id', 'post_id'} for uc in uqs)
            if not has_user_post_unique:
                op.create_unique_constraint('uq_forumnotif_user_post', 'forum_notification', ['user_id', 'post_id'])
        except Exception:
            pass  # SQLite/inspector edge cases – nevadí, nejdeme padnúť

    # --- skupina_pozvanka: len istíme UNIQUE(token) s názvom, ak chýba ---
    try:
        uqs = insp.get_unique_constraints('skupina_pozvanka')
        has_token_unique = any(set(uc.get('column_names', [])) == {'token'} for uc in uqs)
    except Exception:
        has_token_unique = True  # ak nevieme zistiť, radšej neskúšame pridávať

    if not has_token_unique:
        # ak by boli NULL tokeny, urobíme dočasnú výplň, aby UNIQUE prešiel
        op.execute("UPDATE skupina_pozvanka SET token = 'MIG_' || rowid WHERE token IS NULL")
        with op.batch_alter_table('skupina_pozvanka', schema=None) as batch_op:
            batch_op.create_unique_constraint('uq_skupina_pozvanka_token', ['token'])
    # pozn.: ostatné alter_column autogenerate zanechávam bokom, aby sme nerobili
    # zbytočné rebuildy tabuľky v SQLite. Ak ich budeš chcieť, spravíme samostatnú migráciu.


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # skupina_pozvanka: dropni len náš constraint, ak existuje s týmto menom
    try:
        uqs = insp.get_unique_constraints('skupina_pozvanka')
        names = {uc.get('name') for uc in uqs}
    except Exception:
        names = set()

    if 'uq_skupina_pozvanka_token' in names:
        with op.batch_alter_table('skupina_pozvanka', schema=None) as batch_op:
            batch_op.drop_constraint('uq_skupina_pozvanka_token', type_='unique')

    # forum_notification: drop indexy a tabuľku, ak existuje
    try:
        op.drop_index('ix_forum_notification_user_id', table_name='forum_notification')
    except Exception:
        pass
    try:
        op.drop_index('ix_forum_notification_topic_id', table_name='forum_notification')
    except Exception:
        pass
    try:
        op.drop_index('ix_forum_notification_post_id', table_name='forum_notification')
    except Exception:
        pass
    try:
        op.drop_table('forum_notification')
    except Exception:
        pass
