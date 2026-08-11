"""add roles table, convert role columns from enum to fk

Revision ID: 69c7f880a599
Revises: 370658b67021
Create Date: 2026-08-11 20:25:28.976652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69c7f880a599'
down_revision: Union[str, Sequence[str], None] = '370658b67021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLES = [
    {"id": "vendeur", "libelle": "Vendeur boutique", "portee": "boutique", "ordre": 0, "systeme": True},
    {"id": "caissier", "libelle": "Caissier boutique", "portee": "boutique", "ordre": 1, "systeme": True},
    {"id": "gerant", "libelle": "Gérant de boutique", "portee": "boutique", "ordre": 2, "systeme": True},
    {"id": "responsable_achats", "libelle": "Responsable achats siège", "portee": "reseau", "ordre": 3, "systeme": True},
    {"id": "administrateur", "libelle": "Administrateur (siège)", "portee": "reseau", "ordre": 4, "systeme": True},
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'roles',
        sa.Column('id', sa.String(length=60), nullable=False),
        sa.Column('libelle', sa.String(length=120), nullable=False),
        sa.Column('portee', sa.String(length=20), nullable=False),
        sa.Column('ordre', sa.Integer(), nullable=False),
        sa.Column('systeme', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    roles_table = sa.table(
        'roles',
        sa.column('id', sa.String),
        sa.column('libelle', sa.String),
        sa.column('portee', sa.String),
        sa.column('ordre', sa.Integer),
        sa.column('systeme', sa.Boolean),
    )
    op.bulk_insert(roles_table, ROLES)

    # utilisateurs.role et permissions.role étaient des ENUM MySQL — les valeurs existantes
    # ('vendeur', 'caissier', ...) sont des chaînes valides pour la nouvelle colonne VARCHAR,
    # donc pas de transformation de données nécessaire, juste un changement de type + une FK.
    op.execute('ALTER TABLE utilisateurs MODIFY COLUMN role VARCHAR(60) NOT NULL')
    op.create_foreign_key('fk_utilisateurs_role', 'utilisateurs', 'roles', ['role'], ['id'])

    op.execute('ALTER TABLE permissions MODIFY COLUMN role VARCHAR(60) NOT NULL')
    op.create_foreign_key('fk_permissions_role', 'permissions', 'roles', ['role'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_permissions_role', 'permissions', type_='foreignkey')
    op.drop_constraint('fk_utilisateurs_role', 'utilisateurs', type_='foreignkey')

    role_enum = "ENUM('vendeur','caissier','gerant','responsable_achats','administrateur')"
    op.execute(f'ALTER TABLE permissions MODIFY COLUMN role {role_enum} NOT NULL')
    op.execute(f'ALTER TABLE utilisateurs MODIFY COLUMN role {role_enum} NOT NULL')

    op.drop_table('roles')
