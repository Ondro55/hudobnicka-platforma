from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "add_stav_delete_at_to_podujatie"
down_revision = "b149d2c7430c"
branch_labels = None
depends_on = None


def _col_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def _idx_exists(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    idx = [i["name"] for i in insp.get_indexes(table)]
    return index_name in idx


def upgrade():
    # pridaj stĺpce len ak ešte nie sú
    if not _col_exists("podujatie", "stav"):
        op.add_column(
            "podujatie",
            sa.Column("stav", sa.String(length=20), nullable=False, server_default="pending"),
        )

    if not _col_exists("podujatie", "delete_at"):
        op.add_column(
            "podujatie",
            sa.Column("delete_at", sa.DateTime(), nullable=True),
        )

    # doplň default hodnoty, ak by boli NULL (ak stĺpec existoval z predošlého behu)
    op.execute(sa.text("UPDATE podujatie SET stav='pending' WHERE stav IS NULL"))

    # indexy – vytvoriť len ak nie sú
    if not _idx_exists("podujatie", "ix_podujatie_stav"):
        op.create_index("ix_podujatie_stav", "podujatie", ["stav"])
    if not _idx_exists("podujatie", "ix_podujatie_delete_at"):
        op.create_index("ix_podujatie_delete_at", "podujatie", ["delete_at"])

    # POZOR: žiadne alter_column drop default – SQLite to nevie
    # op.alter_column('podujatie', 'stav', server_default=None)  # NEPOUŽÍVAŤ na SQLite


def downgrade():
    # drop indexov a stĺpcov len ak existujú (aby downgrade nespadol)
    if _idx_exists("podujatie", "ix_podujatie_delete_at"):
        op.drop_index("ix_podujatie_delete_at", table_name="podujatie")
    if _idx_exists("podujatie", "ix_podujatie_stav"):
        op.drop_index("ix_podujatie_stav", table_name="podujatie")

    # najprv dropni stĺpce, ak existujú (SQLite to vie len cez recreate, ale Alembic to ošéfuje podľa dialektu)
    if _col_exists("podujatie", "delete_at"):
        op.drop_column("podujatie", "delete_at")
    if _col_exists("podujatie", "stav"):
        op.drop_column("podujatie", "stav")
