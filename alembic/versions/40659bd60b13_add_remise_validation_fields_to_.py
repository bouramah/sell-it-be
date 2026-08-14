"""add remise validation fields to commandes clients

Revision ID: 40659bd60b13
Revises: 2b436d4e9897
Create Date: 2026-08-13 18:14:30.758663

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40659bd60b13'
down_revision: Union[str, Sequence[str], None] = '2b436d4e9897'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Au-delà de ce seuil de remise (10 % sous le prix catalogue), un motif devient obligatoire
# et la commande reste bloquée en attente de validation (gérant ou siège) avant de pouvoir
# être livrée — cf. décision produit du 2026-08-13, même logique anti-fraude que les
# dépenses (SEUIL_VALIDATION_SIEGE dans app/routers/depenses.py).
NEW_PERMISSIONS = [
    {"module_action": "Valider une remise au-delà du seuil", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "complet", "responsable_achats": "aucun", "administrateur": "complet"}},
]


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('commandes_clients', sa.Column('remise_motif', sa.String(length=255), nullable=True))
    op.add_column('commandes_clients', sa.Column(
        'remise_statut', sa.Enum('aucune', 'en_attente', 'validee', name='statutvalidationremise'),
        nullable=False, server_default='aucune',
    ))
    op.add_column('commandes_clients', sa.Column('remise_validee_par', sa.String(length=120), nullable=True))
    op.add_column('commandes_clients', sa.Column('remise_validee_le', sa.DateTime(), nullable=True))

    permissions_table = sa.table(
        'permissions',
        sa.column('module_action', sa.String),
        sa.column('role', sa.String),
        sa.column('droit', sa.String),
        sa.column('ordre', sa.Integer),
    )
    rows = [
        {"module_action": ligne["module_action"], "role": role, "droit": droit, "ordre": ordre}
        for ordre, ligne in enumerate(NEW_PERMISSIONS, start=34)
        for role, droit in ligne["droits"].items()
    ]
    op.bulk_insert(permissions_table, rows)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    for p in NEW_PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE module_action = :m"), {"m": p["module_action"]})

    op.drop_column('commandes_clients', 'remise_validee_le')
    op.drop_column('commandes_clients', 'remise_validee_par')
    op.drop_column('commandes_clients', 'remise_statut')
    op.drop_column('commandes_clients', 'remise_motif')
