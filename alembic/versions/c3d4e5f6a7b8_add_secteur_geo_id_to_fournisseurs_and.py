"""add secteur_geo_id to fournisseurs and utilisateurs

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-14 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('fournisseurs', sa.Column('secteur_geo_id', sa.String(length=40), sa.ForeignKey('secteurs_geo.id', ondelete='SET NULL'), nullable=True))
    op.add_column('utilisateurs', sa.Column('secteur_geo_id', sa.String(length=40), sa.ForeignKey('secteurs_geo.id', ondelete='SET NULL'), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('utilisateurs', 'secteur_geo_id')
    op.drop_column('fournisseurs', 'secteur_geo_id')
