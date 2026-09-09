"""chef secteur et secteur geo referent comptabilite etablissement

Revision ID: a4a82363000f
Revises: e1bc73e90f89
Create Date: 2026-09-08 14:54:59.702731

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a4a82363000f'
down_revision: Union[str, Sequence[str], None] = 'e1bc73e90f89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('secteurs_geo', sa.Column('chef_secteur_id', sa.String(length=40), nullable=True))
    op.create_foreign_key('fk_secteurs_geo_chef_secteur_id', 'secteurs_geo', 'utilisateurs', ['chef_secteur_id'], ['id'], ondelete='SET NULL')

    op.add_column('etablissements', sa.Column('referent_secteur_geo_id', sa.String(length=40), nullable=True))
    op.add_column('etablissements', sa.Column('comptabilite_secteur_geo_id', sa.String(length=40), nullable=True))
    op.create_foreign_key('fk_etablissements_referent_secteur_geo_id', 'etablissements', 'secteurs_geo', ['referent_secteur_geo_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_etablissements_comptabilite_secteur_geo_id', 'etablissements', 'secteurs_geo', ['comptabilite_secteur_geo_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_etablissements_comptabilite_secteur_geo_id', 'etablissements', type_='foreignkey')
    op.drop_constraint('fk_etablissements_referent_secteur_geo_id', 'etablissements', type_='foreignkey')
    op.drop_column('etablissements', 'comptabilite_secteur_geo_id')
    op.drop_column('etablissements', 'referent_secteur_geo_id')

    op.drop_constraint('fk_secteurs_geo_chef_secteur_id', 'secteurs_geo', type_='foreignkey')
    op.drop_column('secteurs_geo', 'chef_secteur_id')
