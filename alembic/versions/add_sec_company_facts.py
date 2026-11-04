"""Store SEC company facts.

Revision ID: add_sec_company_facts
Revises: add_company_news
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa


revision = "add_sec_company_facts"
down_revision = "add_company_news"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_financial_facts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("metric", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Numeric(precision=30, scale=8), nullable=False),
        sa.Column("units", sa.String(length=30), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("filed_date", sa.Date(), nullable=False),
        sa.Column("form", sa.String(length=10), nullable=False),
        sa.Column("accession_number", sa.String(length=25), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["symbol"], ["assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol",
            "metric",
            "accession_number",
            name="uq_company_financial_fact_filing",
        ),
    )
    op.create_index(
        "ix_company_financial_facts_symbol",
        "company_financial_facts",
        ["symbol"],
    )
    op.create_index(
        "idx_company_financial_fact_symbol_metric_period",
        "company_financial_facts",
        ["symbol", "metric", "period_end"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_company_financial_fact_symbol_metric_period",
        table_name="company_financial_facts",
    )
    op.drop_index(
        "ix_company_financial_facts_symbol",
        table_name="company_financial_facts",
    )
    op.drop_table("company_financial_facts")
