"""Add daily exchange rates

Revision ID: add_exchange_rates
Revises: add_macro_indicators
Create Date: 2026-11-02

"""
from alembic import op
import sqlalchemy as sa


revision = "add_exchange_rates"
down_revision = "add_macro_indicators"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("quote_currency", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "date",
            "base_currency",
            "quote_currency",
            name="uq_exchange_rate_date_pair",
        ),
    )
    op.create_index(
        "idx_exchange_rate_pair_date",
        "exchange_rates",
        ["base_currency", "quote_currency", "date"],
    )


def downgrade() -> None:
    op.drop_index("idx_exchange_rate_pair_date", table_name="exchange_rates")
    op.drop_table("exchange_rates")
