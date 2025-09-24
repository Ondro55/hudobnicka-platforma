"""extend user theme choices (green, red)

Revision ID: 779b1c680b82
Revises: 7e3f316b3cb9
Create Date: 2025-09-23 16:27:21.213245

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '779b1c680b82'
down_revision = '7e3f316b3cb9'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    existing = {c.get("name") for c in insp.get_check_constraints("pouzivatel")}

    with op.batch_alter_table("pouzivatel") as b:
        if "ck_user_theme" in existing:
            b.drop_constraint("ck_user_theme", type_="check")
        b.create_check_constraint(
            "ck_user_theme",
            "theme IN ('system','light','dark','blue','green','red')",
        )

def downgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    existing = {c.get("name") for c in insp.get_check_constraints("pouzivatel")}

    with op.batch_alter_table("pouzivatel") as b:
        if "ck_user_theme" in existing:
            b.drop_constraint("ck_user_theme", type_="check")
        b.create_check_constraint(
            "ck_user_theme",
            "theme IN ('system','light','dark','blue')",
        )