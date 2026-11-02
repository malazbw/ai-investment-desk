"""Add macro_indicators table

Revision ID: add_macro_indicators
Revises: 3e54fca08596
Create Date: 2024-11-01 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_macro_indicators'
down_revision = '3e54fca08596'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'macro_indicators',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('series_id', sa.String(length=10), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('value', sa.Numeric(precision=15, scale=4), nullable=False),
        sa.Column('units', sa.String(length=50), nullable=True),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_macro_series_date', 'macro_indicators', ['series_id', 'date'])
    op.create_index('idx_macro_date', 'macro_indicators', ['date'])


def downgrade() -> None:
    op.drop_index('idx_macro_date', table_name='macro_indicators')
    op.drop_index('idx_macro_series_date', table_name='macro_indicators')
    op.drop_table('macro_indicators')
