"""add geographic hierarchy region ville commune quartier secteur

Revision ID: 1ffc630300b6
Revises: 6afe02637b22
Create Date: 2026-08-14 02:40:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ffc630300b6'
down_revision: Union[str, Sequence[str], None] = '6afe02637b22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Découpage administratif Région > Ville > Commune > Quartier > Secteur — localisation précise
# des clients pour les tournées de livraison et la future appli mobile client. Seed les 8 régions
# administratives réelles de Guinée (dont Conakry, zone spéciale) pour démarrer ; villes/communes/
# quartiers/secteurs restent à saisir via l'écran de gestion des référentiels géographiques.

REGIONS_GUINEE = [
    "Conakry", "Boké", "Kindia", "Mamou", "Labé", "Faranah", "Kankan", "N'Zérékoré",
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'regions',
        sa.Column('id', sa.String(length=40), primary_key=True),
        sa.Column('nom', sa.String(length=120), nullable=False, unique=True),
    )
    op.create_table(
        'villes',
        sa.Column('id', sa.String(length=40), primary_key=True),
        sa.Column('nom', sa.String(length=120), nullable=False),
        sa.Column('region_id', sa.String(length=40), sa.ForeignKey('regions.id', ondelete='CASCADE'), nullable=False),
    )
    op.create_table(
        'communes',
        sa.Column('id', sa.String(length=40), primary_key=True),
        sa.Column('nom', sa.String(length=120), nullable=False),
        sa.Column('ville_id', sa.String(length=40), sa.ForeignKey('villes.id', ondelete='CASCADE'), nullable=False),
    )
    op.create_table(
        'quartiers_geo',
        sa.Column('id', sa.String(length=40), primary_key=True),
        sa.Column('nom', sa.String(length=120), nullable=False),
        sa.Column('commune_id', sa.String(length=40), sa.ForeignKey('communes.id', ondelete='CASCADE'), nullable=False),
    )
    op.create_table(
        'secteurs_geo',
        sa.Column('id', sa.String(length=40), primary_key=True),
        sa.Column('nom', sa.String(length=120), nullable=False),
        sa.Column('quartier_id', sa.String(length=40), sa.ForeignKey('quartiers_geo.id', ondelete='CASCADE'), nullable=False),
    )
    op.add_column('clients', sa.Column('secteur_geo_id', sa.String(length=40), sa.ForeignKey('secteurs_geo.id', ondelete='SET NULL'), nullable=True))

    conn = op.get_bind()
    regions_table = sa.table('regions', sa.column('id', sa.String), sa.column('nom', sa.String))
    conn.execute(regions_table.insert(), [{'id': uuid.uuid4().hex[:8], 'nom': nom} for nom in REGIONS_GUINEE])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('clients', 'secteur_geo_id')
    op.drop_table('secteurs_geo')
    op.drop_table('quartiers_geo')
    op.drop_table('communes')
    op.drop_table('villes')
    op.drop_table('regions')
