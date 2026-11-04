"""Store publisher-provided news summary snippets.

Revision ID: add_news_description
Revises: add_sec_company_facts
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa


revision = "add_news_description"
down_revision = "add_sec_company_facts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_news",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("company_news", "description")
