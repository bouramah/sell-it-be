"""expand permissions matrix to full cdc rows and fix stock read only

Revision ID: ca026b9db995
Revises: 8d9f3b9c340c
Create Date: 2026-08-11 18:53:11.418702

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca026b9db995'
down_revision: Union[str, Sequence[str], None] = '8d9f3b9c340c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_PERMISSIONS = [
    {"module_action": "Valider un encaissement / paiement", "droits": {"vendeur": "aucun", "caissier": "complet", "gerant": "complet", "responsable_achats": "aucun", "administrateur": "complet"}},
    {"module_action": "Créer / modifier une commande client", "droits": {"vendeur": "complet", "caissier": "complet", "gerant": "complet", "responsable_achats": "aucun", "administrateur": "complet"}},
    {"module_action": "Enregistrer une dette / créance client", "droits": {"vendeur": "complet", "caissier": "complet", "gerant": "complet", "responsable_achats": "aucun", "administrateur": "complet"}},
    {"module_action": "Enregistrer un remboursement de dette", "droits": {"vendeur": "aucun", "caissier": "complet", "gerant": "complet", "responsable_achats": "aucun", "administrateur": "complet"}},
    {"module_action": "Réceptionner un transfert de stock", "droits": {"vendeur": "complet", "caissier": "aucun", "gerant": "complet", "responsable_achats": "aucun", "administrateur": "complet"}},
    {"module_action": "Gérer les livraisons (affectation livreur, suivi)", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "complet", "responsable_achats": "lecture_seule", "administrateur": "complet"}},
    {"module_action": "Enregistrer une dépense de boutique", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "complet", "responsable_achats": "aucun", "administrateur": "complet"}},
    {"module_action": "Consulter le dashboard de sa boutique", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "complet", "responsable_achats": "complet", "administrateur": "complet"}},
    {"module_action": "Consulter la vue globale des mouvements de caisse/stock", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "aucun", "responsable_achats": "partiel", "administrateur": "complet"}},
    {"module_action": "Consulter la comptabilité de sa boutique", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "complet", "responsable_achats": "aucun", "administrateur": "complet"}},
    {"module_action": "Consulter la comptabilité consolidée du réseau", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "aucun", "responsable_achats": "partiel", "administrateur": "complet"}},
    {"module_action": "Paramétrer les promotions et tarifs", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "partiel", "responsable_achats": "complet", "administrateur": "complet"}},
    {"module_action": "Accéder aux modules IA", "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "lecture_seule", "responsable_achats": "complet", "administrateur": "complet"}},
]


def upgrade() -> None:
    """Upgrade schema."""
    # Corrige un écart avec le CDC : le responsable achats n'a qu'un accès en lecture seule
    # au stock de boutique (validation/consultation, pas de modification directe).
    op.execute(
        "UPDATE permissions SET droit = 'lecture_seule' "
        "WHERE module_action = 'Consulter le stock de sa boutique' AND role = 'responsable_achats'"
    )

    permissions_table = sa.table(
        'permissions',
        sa.column('module_action', sa.String),
        sa.column('role', sa.String),
        sa.column('droit', sa.String),
        sa.column('ordre', sa.Integer),
    )
    rows = [
        {"module_action": ligne["module_action"], "role": role, "droit": droit, "ordre": ordre}
        for ordre, ligne in enumerate(NEW_PERMISSIONS, start=10)
        for role, droit in ligne["droits"].items()
    ]
    op.bulk_insert(permissions_table, rows)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "UPDATE permissions SET droit = 'complet' "
        "WHERE module_action = 'Consulter le stock de sa boutique' AND role = 'responsable_achats'"
    )
    conn = op.get_bind()
    for p in NEW_PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE module_action = :m"), {"m": p["module_action"]})
