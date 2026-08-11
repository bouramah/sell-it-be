"""split transfert row and add remaining action rows to permissions matrix

Revision ID: 370658b67021
Revises: a81d63811f14
Create Date: 2026-08-11 19:28:08.359574

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '370658b67021'
down_revision: Union[str, Sequence[str], None] = 'a81d63811f14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# "Initier un transfert de stock" mélangeait la demande (gérant) et la validation
# (responsable achats) dans une seule ligne "partiel" — l'app applique en réalité deux
# rôles distincts pour deux actions distinctes (cf. app/routers/transferts.py), donc on
# la remplace par deux lignes propres.
OLD_ROW = "Initier un transfert de stock"

REPLACEMENT_ROWS = [
    {"module_action": "Initier un transfert de stock (demande)", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "complet", "responsable_achats": "aucun", "administrateur": "complet"}},
    {"module_action": "Valider un transfert de stock (autoriser l'envoi)", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "aucun", "responsable_achats": "complet", "administrateur": "complet"}},
]

NEW_PERMISSIONS = [
    {"module_action": "Réceptionner une commande fournisseur", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "partiel", "responsable_achats": "partiel", "administrateur": "complet"}},
    {"module_action": "Valider ou refuser une promotion", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "aucun", "responsable_achats": "complet", "administrateur": "complet"}},
    {"module_action": "Modifier le stock (ajout de ligne, mouvement manuel, inventaire)", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "complet", "responsable_achats": "aucun", "administrateur": "complet"}},
    {"module_action": "Gérer les référentiels (villes, catégories, motifs…)", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "aucun", "responsable_achats": "aucun", "administrateur": "complet"}},
    {"module_action": "Consulter le journal d'audit et gérer les paramètres de sécurité", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "aucun", "responsable_achats": "aucun", "administrateur": "complet"}},
    {"module_action": "Enregistrer un mouvement de caisse manuel", "droits": {"vendeur": "aucun", "caissier": "complet", "gerant": "complet", "responsable_achats": "aucun", "administrateur": "complet"}},
]


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM permissions WHERE module_action = :m"), {"m": OLD_ROW})

    permissions_table = sa.table(
        'permissions',
        sa.column('module_action', sa.String),
        sa.column('role', sa.String),
        sa.column('droit', sa.String),
        sa.column('ordre', sa.Integer),
    )
    all_new = REPLACEMENT_ROWS + NEW_PERMISSIONS
    rows = [
        {"module_action": ligne["module_action"], "role": role, "droit": droit, "ordre": ordre}
        for ordre, ligne in enumerate(all_new, start=26)
        for role, droit in ligne["droits"].items()
    ]
    op.bulk_insert(permissions_table, rows)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    for p in REPLACEMENT_ROWS + NEW_PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE module_action = :m"), {"m": p["module_action"]})

    permissions_table = sa.table(
        'permissions',
        sa.column('module_action', sa.String),
        sa.column('role', sa.String),
        sa.column('droit', sa.String),
        sa.column('ordre', sa.Integer),
    )
    old_droits = {"vendeur": "aucun", "caissier": "aucun", "gerant": "partiel", "responsable_achats": "partiel", "administrateur": "complet"}
    rows = [{"module_action": OLD_ROW, "role": role, "droit": droit, "ordre": 5} for role, droit in old_droits.items()]
    op.bulk_insert(permissions_table, rows)
