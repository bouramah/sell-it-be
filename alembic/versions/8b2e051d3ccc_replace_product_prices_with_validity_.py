"""replace product prices with validity period based pricing

Revision ID: 8b2e051d3ccc
Revises: b612986e5151
Create Date: 2026-08-13 21:13:09.953287

"""
import uuid
from datetime import date
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b2e051d3ccc'
down_revision: Union[str, Sequence[str], None] = 'b612986e5151'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Les prix changent souvent et il faut pouvoir dire, pour un audit, "quel était le prix catalogue
# à la date de cette vente" — décision produit du 2026-08-13 : les prix deviennent des périodes de
# validité [date_debut, date_fin], sans chevauchement possible pour un même (produit, boutique,
# palier), au lieu d'une simple valeur modifiable. Remplace prix_detail/semi_gros/gros sur
# ProduitDB et la table prix_boutiques (introduits plus tôt dans la même session).

PALIER_ENUM = sa.Enum('detail', 'semi_gros', 'gros', name='palierprix')


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'prix_periodes',
        sa.Column('id', sa.String(length=40), primary_key=True),
        sa.Column('produit_id', sa.String(length=40), sa.ForeignKey('produits.id', ondelete='CASCADE'), nullable=False),
        sa.Column('boutique_id', sa.String(length=40), sa.ForeignKey('boutiques.id', ondelete='CASCADE'), nullable=True),
        sa.Column('palier', PALIER_ENUM, nullable=False),
        sa.Column('prix', sa.Float(), nullable=False),
        sa.Column('date_debut', sa.Date(), nullable=False),
        sa.Column('date_fin', sa.Date(), nullable=True),
        sa.Column('modifie_par', sa.String(length=160), nullable=False),
        sa.Column('cree_le', sa.DateTime(), server_default=sa.func.now()),
    )

    op.add_column(
        'lignes_commandes_clients',
        sa.Column('palier', sa.Enum('detail', 'semi_gros', 'gros', name='palierprix_lignes'), nullable=False, server_default='detail'),
    )

    conn = op.get_bind()
    today = date.today().isoformat()

    prix_periodes_table = sa.table(
        'prix_periodes',
        sa.column('id', sa.String), sa.column('produit_id', sa.String), sa.column('boutique_id', sa.String),
        sa.column('palier', sa.String), sa.column('prix', sa.Float),
        sa.column('date_debut', sa.Date), sa.column('date_fin', sa.Date), sa.column('modifie_par', sa.String),
    )
    rows = []

    produits = conn.execute(sa.text("SELECT id, prix_detail, prix_semi_gros, prix_gros FROM produits")).fetchall()
    for p in produits:
        for palier, prix in [('detail', p.prix_detail), ('semi_gros', p.prix_semi_gros), ('gros', p.prix_gros)]:
            rows.append({
                'id': uuid.uuid4().hex[:8], 'produit_id': p.id, 'boutique_id': None,
                'palier': palier, 'prix': prix, 'date_debut': today, 'date_fin': None,
                'modifie_par': 'Migration automatique',
            })

    overrides = conn.execute(sa.text("SELECT boutique_id, produit_id, prix_detail, prix_semi_gros, prix_gros FROM prix_boutiques")).fetchall()
    for o in overrides:
        for palier, prix in [('detail', o.prix_detail), ('semi_gros', o.prix_semi_gros), ('gros', o.prix_gros)]:
            if prix is None:
                continue
            rows.append({
                'id': uuid.uuid4().hex[:8], 'produit_id': o.produit_id, 'boutique_id': o.boutique_id,
                'palier': palier, 'prix': prix, 'date_debut': today, 'date_fin': None,
                'modifie_par': 'Migration automatique',
            })

    if rows:
        op.bulk_insert(prix_periodes_table, rows)

    op.drop_table('prix_boutiques')
    op.drop_column('produits', 'prix_gros')
    op.drop_column('produits', 'prix_semi_gros')
    op.drop_column('produits', 'prix_detail')


def downgrade() -> None:
    """Downgrade schema — best effort : reprend la période réseau/boutique ouverte la plus
    récente par (produit, palier) ; l'historique complet des périodes est perdu."""
    op.add_column('produits', sa.Column('prix_detail', sa.Float(), nullable=True))
    op.add_column('produits', sa.Column('prix_semi_gros', sa.Float(), nullable=True))
    op.add_column('produits', sa.Column('prix_gros', sa.Float(), nullable=True))

    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE produits p
        SET prix_detail = (
            SELECT prix FROM prix_periodes
            WHERE produit_id = p.id AND boutique_id IS NULL AND palier = 'detail'
            ORDER BY date_debut DESC LIMIT 1
        ),
        prix_semi_gros = (
            SELECT prix FROM prix_periodes
            WHERE produit_id = p.id AND boutique_id IS NULL AND palier = 'semi_gros'
            ORDER BY date_debut DESC LIMIT 1
        ),
        prix_gros = (
            SELECT prix FROM prix_periodes
            WHERE produit_id = p.id AND boutique_id IS NULL AND palier = 'gros'
            ORDER BY date_debut DESC LIMIT 1
        )
    """))
    op.alter_column('produits', 'prix_detail', existing_type=sa.Float(), nullable=False)
    op.alter_column('produits', 'prix_semi_gros', existing_type=sa.Float(), nullable=False)
    op.alter_column('produits', 'prix_gros', existing_type=sa.Float(), nullable=False)

    op.create_table(
        'prix_boutiques',
        sa.Column('boutique_id', sa.String(length=40), sa.ForeignKey('boutiques.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('produit_id', sa.String(length=40), sa.ForeignKey('produits.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('prix_detail', sa.Float(), nullable=True),
        sa.Column('prix_semi_gros', sa.Float(), nullable=True),
        sa.Column('prix_gros', sa.Float(), nullable=True),
    )
    conn.execute(sa.text("""
        INSERT INTO prix_boutiques (boutique_id, produit_id, prix_detail, prix_semi_gros, prix_gros)
        SELECT DISTINCT boutique_id, produit_id, NULL, NULL, NULL
        FROM prix_periodes WHERE boutique_id IS NOT NULL
    """))
    for palier in ('detail', 'semi_gros', 'gros'):
        conn.execute(sa.text(f"""
            UPDATE prix_boutiques pb
            SET prix_{palier} = (
                SELECT prix FROM prix_periodes
                WHERE produit_id = pb.produit_id AND boutique_id = pb.boutique_id AND palier = '{palier}'
                ORDER BY date_debut DESC LIMIT 1
            )
        """))

    op.drop_column('lignes_commandes_clients', 'palier')
    op.drop_table('prix_periodes')
