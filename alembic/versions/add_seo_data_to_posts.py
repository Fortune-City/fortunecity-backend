"""Add seo_data to blog_posts

Revision ID: add_seo_data
Revises: 
Create Date: 2026-02-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_seo_data'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add seo_data column to blog_posts table
    op.add_column('blog_posts', sa.Column('seo_data', sa.JSON(), nullable=True))


def downgrade():
    # Remove seo_data column from blog_posts table
    op.drop_column('blog_posts', 'seo_data')
