"""add produit fournisseur client rows to permissions matrix

Revision ID: a81d63811f14
Revises: ca026b9db995
Create Date: 2026-08-11 19:22:29.571428

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a81d63811f14'
down_revision: Union[str, Sequence[str], None] = 'ca026b9db995'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Ces trois actions n'ont pas de ligne dédiée dans la matrice indicative du CDC (§3.3) —
# seules "Consulter le stock", "Créer une commande fournisseur/client", etc. y figurent.
# Ajoutées ici pour que la matrice reflète l'intégralité de ce qui est réellement appliqué
# par l'application (cf. app/routers/produits.py, reseau.py, clients.py).
NEW_PERMISSIONS = [
    {"module_action": "Gérer le catalogue produits (créer/modifier/supprimer)", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "complet", "responsable_achats": "complet", "administrateur": "complet"}},
    {"module_action": "Gérer les fournisseurs (créer/modifier/supprimer)", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "complet", "responsable_achats": "complet", "administrateur": "complet"}},
    {"module_action": "Créer / modifier une fiche client", "droits": {"vendeur": "complet", "caissier": "complet", "gerant": "complet", "responsable_achats": "aucun", "administrateur": "complet"}},
]


def upgrade() -> None:
    """Upgrade schema."""
    permissions_table = sa.table(
        'permissions',
        sa.column('module_action', sa.String),
        sa.column('role', sa.String),
        sa.column('droit', sa.String),
        sa.column('ordre', sa.Integer),
    )
    rows = [
        {"module_action": ligne["module_action"], "role": role, "droit": droit, "ordre": ordre}
        for ordre, ligne in enumerate(NEW_PERMISSIONS, start=23)
        for role, droit in ligne["droits"].items()
    ]
    op.bulk_insert(permissions_table, rows)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    for p in NEW_PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE module_action = :m"), {"m": p["module_action"]})
