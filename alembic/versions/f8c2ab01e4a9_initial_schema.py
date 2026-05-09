"""initial_schema

Revision ID: f8c2ab01e4a9
Revises:
Create Date: 2026-02-09

Deploy note: если таблицы уже созданы через create_all до Alembic, один раз выполните
``alembic stamp f8c2ab01e4a9`` вместо upgrade, затем следующие ревизии — как обычно.
"""

from alembic import op
import sqlalchemy as sa

revision = "f8c2ab01e4a9"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "domains",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.Column("track_http", sa.Boolean(), nullable=True),
        sa.Column("track_https", sa.Boolean(), nullable=True),
        sa.Column("track_ssl", sa.Boolean(), nullable=True),
        sa.Column("track_whois", sa.Boolean(), nullable=True),
        sa.Column("ssl_warn_days", sa.Integer(), nullable=True),
        sa.Column("whois_warn_days", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "user_id", name="uix_user_domain"),
    )
    op.create_index(op.f("ix_domains_id"), "domains", ["id"], unique=False)
    op.create_index(op.f("ix_domains_name"), "domains", ["name"], unique=False)
    op.create_index(op.f("ix_domains_user_id"), "domains", ["user_id"], unique=False)

    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "track_http",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "track_https",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "track_ssl",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "track_whois",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "ssl_warn_days",
            sa.Integer(),
            server_default=sa.text("15"),
            nullable=False,
        ),
        sa.Column(
            "whois_warn_days",
            sa.Integer(),
            server_default=sa.text("30"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
    op.drop_index(op.f("ix_domains_user_id"), table_name="domains")
    op.drop_index(op.f("ix_domains_name"), table_name="domains")
    op.drop_index(op.f("ix_domains_id"), table_name="domains")
    op.drop_table("domains")
