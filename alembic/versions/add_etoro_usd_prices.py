"""Add eToro instrument mapping and USD price metadata.

Revision ID: add_etoro_usd_prices
Revises: add_exchange_rates
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa


revision = "add_etoro_usd_prices"
down_revision = "add_exchange_rates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assets",
        sa.Column("etoro_instrument_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "uq_assets_etoro_instrument_id",
        "assets",
        ["etoro_instrument_id"],
        unique=True,
    )
    op.add_column(
        "prices",
        sa.Column("currency", sa.String(length=3), nullable=True),
    )
    with op.batch_alter_table("holdings") as batch_op:
        batch_op.alter_column(
            "current_price",
            existing_type=sa.Numeric(precision=15, scale=4),
            type_=sa.Numeric(precision=20, scale=8),
            existing_nullable=True,
        )
    with op.batch_alter_table("prices") as batch_op:
        batch_op.alter_column(
            "price",
            existing_type=sa.Numeric(precision=15, scale=4),
            type_=sa.Numeric(precision=20, scale=8),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("prices") as batch_op:
        batch_op.alter_column(
            "price",
            existing_type=sa.Numeric(precision=20, scale=8),
            type_=sa.Numeric(precision=15, scale=4),
            existing_nullable=False,
        )
    with op.batch_alter_table("holdings") as batch_op:
        batch_op.alter_column(
            "current_price",
            existing_type=sa.Numeric(precision=20, scale=8),
            type_=sa.Numeric(precision=15, scale=4),
            existing_nullable=True,
        )
    op.drop_column("prices", "currency")
    op.drop_index("uq_assets_etoro_instrument_id", table_name="assets")
    op.drop_column("assets", "etoro_instrument_id")
