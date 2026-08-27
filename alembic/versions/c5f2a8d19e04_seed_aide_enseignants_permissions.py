"""seed permissions for aide enseignants module actions + grades_enseignants referentiel

Revision ID: c5f2a8d19e04
Revises: b3e7c1f4a982
Create Date: 2026-08-27 09:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c5f2a8d19e04'
down_revision: Union[str, Sequence[str], None] = 'b3e7c1f4a982'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Gestion (écoles, fiches enseignant) confiée à l'administrateur et au gérant, comme les autres
# modules opérationnels du quotidien ; le barème (paramétrage financier sensible) reste réservé
# à l'administrateur, même logique que la TVA (ParametreFiscalDB).
NEW_PERMISSIONS = [
    {
        "module_action": "Gérer les écoles partenaires et leurs garants",
        "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "complet", "responsable_achats": "aucun", "livreur": "aucun", "administrateur": "complet"},
    },
    {
        "module_action": "Gérer les enseignants bénéficiaires (aide aux enseignants)",
        "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "complet", "responsable_achats": "aucun", "livreur": "aucun", "administrateur": "complet"},
    },
    {
        "module_action": "Paramétrer le barème de plafond de crédit enseignants",
        "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "aucun", "responsable_achats": "aucun", "livreur": "aucun", "administrateur": "complet"},
    },
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
        for ordre, ligne in enumerate(NEW_PERMISSIONS, start=100)
        for role, droit in ligne["droits"].items()
    ]
    op.bulk_insert(permissions_table, rows)
    # La catégorie de référentiel "grades_enseignants" n'a pas besoin de migration : elle est
    # déclarée vide dans app/data/fixtures.py::REFERENTIELS et apparaît automatiquement dans
    # Paramètres → Référentiels (cf. parametres.py::_managed_categories) pour que l'administrateur
    # y saisisse les grades/échelons réels de ses écoles partenaires.


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    for p in NEW_PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE module_action = :m"), {"m": p["module_action"]})
