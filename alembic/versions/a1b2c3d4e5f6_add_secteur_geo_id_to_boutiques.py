"""add secteur_geo_id to boutiques

Revision ID: a1b2c3d4e5f6
Revises: c440b4c40882
Create Date: 2026-08-14 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c440b4c40882'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('boutiques', sa.Column('secteur_geo_id', sa.String(length=40), sa.ForeignKey('secteurs_geo.id', ondelete='SET NULL'), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('boutiques', 'secteur_geo_id')
