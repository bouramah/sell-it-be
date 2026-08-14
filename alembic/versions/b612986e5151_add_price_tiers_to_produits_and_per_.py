"""add price tiers to produits and per boutique price overrides

Revision ID: b612986e5151
Revises: 40659bd60b13
Create Date: 2026-08-13 20:01:24.443788

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b612986e5151'
down_revision: Union[str, Sequence[str], None] = '40659bd60b13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Un sac de riz ne se vend pas au même prix à Conakry qu'à Kissidougou, et un client qui en
# achète 50 ne paie pas le même prix unitaire qu'un client qui en achète 1 — décision produit
# du 2026-08-13 : chaque produit porte 3 prix de référence réseau (détail/semi-gros/gros),
# chaque boutique peut les surcharger indépendamment (table prix_boutiques, valeurs NULL =
# hérite du réseau).


def upgrade() -> None:
    """Upgrade schema."""
    # 1) Nouvelles colonnes nullable, peuplées depuis l'ancien prix unique, puis verrouillées NOT NULL.
    op.add_column('produits', sa.Column('prix_detail', sa.Float(), nullable=True))
    op.add_column('produits', sa.Column('prix_semi_gros', sa.Float(), nullable=True))
    op.add_column('produits', sa.Column('prix_gros', sa.Float(), nullable=True))
    op.add_column('produits', sa.Column('seuil_semi_gros', sa.Integer(), nullable=False, server_default='10'))
    op.add_column('produits', sa.Column('seuil_gros', sa.Integer(), nullable=False, server_default='50'))

    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE produits SET prix_detail = prix, prix_semi_gros = prix, prix_gros = prix WHERE prix_detail IS NULL"
    ))

    op.alter_column('produits', 'prix_detail', existing_type=sa.Float(), nullable=False)
    op.alter_column('produits', 'prix_semi_gros', existing_type=sa.Float(), nullable=False)
    op.alter_column('produits', 'prix_gros', existing_type=sa.Float(), nullable=False)
    op.drop_column('produits', 'prix')

    # 2) Surcharges de prix par boutique — toute colonne NULL hérite du prix réseau ci-dessus.
    op.create_table(
        'prix_boutiques',
        sa.Column('boutique_id', sa.String(length=40), sa.ForeignKey('boutiques.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('produit_id', sa.String(length=40), sa.ForeignKey('produits.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('prix_detail', sa.Float(), nullable=True),
        sa.Column('prix_semi_gros', sa.Float(), nullable=True),
        sa.Column('prix_gros', sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('prix_boutiques')

    op.add_column('produits', sa.Column('prix', sa.Float(), nullable=True))
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE produits SET prix = prix_detail"))
    op.alter_column('produits', 'prix', existing_type=sa.Float(), nullable=False)

    op.drop_column('produits', 'seuil_gros')
    op.drop_column('produits', 'seuil_semi_gros')
    op.drop_column('produits', 'prix_gros')
    op.drop_column('produits', 'prix_semi_gros')
    op.drop_column('produits', 'prix_detail')
