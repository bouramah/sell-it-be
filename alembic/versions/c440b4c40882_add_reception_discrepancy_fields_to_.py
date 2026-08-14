"""add reception discrepancy fields to transferts stock

Revision ID: c440b4c40882
Revises: d1b95cf72cda
Create Date: 2026-08-14 04:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c440b4c40882'
down_revision: Union[str, Sequence[str], None] = 'd1b95cf72cda'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Écart à la réception d'un transfert (casse/perte en transit) — CDC 3.9, gap identifié lors de
# l'audit CDC : la confirmation de réception était binaire, sans ajustement de quantité ni motif.


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('transferts_stock', sa.Column('quantite_recue', sa.Integer(), nullable=True))
    op.add_column('transferts_stock', sa.Column('motif_ecart', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('transferts_stock', 'motif_ecart')
    op.drop_column('transferts_stock', 'quantite_recue')
