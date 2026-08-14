"""add purchase price periods by supplier

Revision ID: 6afe02637b22
Revises: 8b2e051d3ccc
Create Date: 2026-08-14 02:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6afe02637b22'
down_revision: Union[str, Sequence[str], None] = '8b2e051d3ccc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Un fournisseur peut consentir un meilleur prix selon le volume acheté — même mécanique que
# prix_periodes côté vente (palier + période datée, sans chevauchement), mais toujours rattaché
# à un fournisseur précis (pas de "prix réseau" côté achat).


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'prix_achats',
        sa.Column('id', sa.String(length=40), primary_key=True),
        sa.Column('produit_id', sa.String(length=40), sa.ForeignKey('produits.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fournisseur_id', sa.String(length=40), sa.ForeignKey('fournisseurs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('palier', sa.Enum('detail', 'semi_gros', 'gros', name='palierprix_achats'), nullable=False),
        sa.Column('prix', sa.Float(), nullable=False),
        sa.Column('date_debut', sa.Date(), nullable=False),
        sa.Column('date_fin', sa.Date(), nullable=True),
        sa.Column('modifie_par', sa.String(length=160), nullable=False),
        sa.Column('cree_le', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('prix_achats')
