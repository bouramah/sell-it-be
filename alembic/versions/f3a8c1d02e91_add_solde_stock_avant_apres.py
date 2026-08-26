"""add solde_avant/solde_apres and stock_avant/stock_apres to mouvements

Revision ID: f3a8c1d02e91
Revises: 9ec100c02830
Create Date: 2026-08-26 21:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f3a8c1d02e91'
down_revision: Union[str, Sequence[str], None] = '9ec100c02830'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('mouvements_caisse', sa.Column('solde_avant', sa.Float(), nullable=False, server_default='0'))
    op.add_column('mouvements_caisse', sa.Column('solde_apres', sa.Float(), nullable=False, server_default='0'))
    op.add_column('mouvements_stock', sa.Column('stock_avant', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('mouvements_stock', sa.Column('stock_apres', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('mouvements_stock', 'stock_apres')
    op.drop_column('mouvements_stock', 'stock_avant')
    op.drop_column('mouvements_caisse', 'solde_apres')
    op.drop_column('mouvements_caisse', 'solde_avant')
