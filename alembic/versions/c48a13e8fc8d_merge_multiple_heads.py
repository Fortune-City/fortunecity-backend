"""Merge multiple heads

Revision ID: c48a13e8fc8d
Revises: 80d1260f1ebf, add_seo_data
Create Date: 2026-02-17 11:33:22.461531

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c48a13e8fc8d'
down_revision: Union[str, Sequence[str], None] = ('80d1260f1ebf', 'add_seo_data')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
