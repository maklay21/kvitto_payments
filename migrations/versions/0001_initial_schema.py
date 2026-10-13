"""Create tariffs and payments.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tariffs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_tariffs_price_nonnegative"),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("tariff_id", sa.String(length=32), sa.ForeignKey("tariffs.id"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("discount", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        sa.Column("installment_months", sa.Integer(), nullable=True),
        sa.Column("schedule", sa.JSON(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False, index=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_payments_amount_nonnegative"),
        sa.CheckConstraint("discount >= 0", name="ck_payments_discount_nonnegative"),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed', 'refunded')",
            name="ck_payments_status",
        ),
        sa.CheckConstraint(
            "method IN ('card', 'sbp', 'installment')",
            name="ck_payments_method",
        ),
        sa.CheckConstraint(
            "installment_months IS NULL OR installment_months IN (3, 6, 12)",
            name="ck_payments_installment_months",
        ),
    )


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("tariffs")
