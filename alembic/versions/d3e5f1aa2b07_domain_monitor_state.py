"""domain_monitor_state

Revision ID: d3e5f1aa2b07
Revises: f8c2ab01e4a9
Create Date: 2026-05-10

"""
from alembic import op
import sqlalchemy as sa

revision = "d3e5f1aa2b07"
down_revision = "f8c2ab01e4a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "domains",
        sa.Column("last_avail_check_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("last_avail_ok", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("last_avail_alert_signature", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("last_avail_alert_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("last_expiry_check_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("last_expiry_ok", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("last_expiry_alert_signature", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "domains",
        sa.Column("last_expiry_alert_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("domains", "last_expiry_alert_at")
    op.drop_column("domains", "last_expiry_alert_signature")
    op.drop_column("domains", "last_expiry_ok")
    op.drop_column("domains", "last_expiry_check_at")
    op.drop_column("domains", "last_avail_alert_at")
    op.drop_column("domains", "last_avail_alert_signature")
    op.drop_column("domains", "last_avail_ok")
    op.drop_column("domains", "last_avail_check_at")
