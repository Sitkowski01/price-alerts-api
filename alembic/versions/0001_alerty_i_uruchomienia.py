"""Tabele alertów i uruchomień

Revision ID: 0001
Revises:
Create Date: 2026-08-27
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 6), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="armed"),
        sa.Column("note", sa.String(280), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("threshold > 0", name="ck_alerts_threshold_positive"),
        sa.CheckConstraint("direction in ('above','below')", name="ck_alerts_direction"),
        sa.CheckConstraint("status in ('armed','triggered','disabled')", name="ck_alerts_status"),
    )
    op.create_index("ix_alerts_ticker_status", "alerts", ["ticker", "status"])

    op.create_table(
        "triggers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "alert_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alerts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column("quote_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("alert_id", "quote_ts", name="uq_triggers_alert_quote_ts"),
    )
    op.create_index("ix_triggers_alert_created", "triggers", ["alert_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_triggers_alert_created", table_name="triggers")
    op.drop_table("triggers")
    op.drop_index("ix_alerts_ticker_status", table_name="alerts")
    op.drop_table("alerts")
