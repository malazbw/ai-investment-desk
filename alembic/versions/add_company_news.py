"""Add company news storage.

Revision ID: add_company_news
Revises: add_etoro_usd_prices
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa


revision = "add_company_news"
down_revision = "add_etoro_usd_prices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_news",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("headline", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("published_date", sa.DateTime(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["symbol"], ["assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_index("ix_company_news_symbol", "company_news", ["symbol"])
    op.create_index(
        "idx_company_news_symbol_date",
        "company_news",
        ["symbol", "published_date"],
    )
    op.create_index("idx_company_news_date", "company_news", ["published_date"])


def downgrade() -> None:
    op.drop_index("idx_company_news_date", table_name="company_news")
    op.drop_index("idx_company_news_symbol_date", table_name="company_news")
    op.drop_index("ix_company_news_symbol", table_name="company_news")
    op.drop_table("company_news")
