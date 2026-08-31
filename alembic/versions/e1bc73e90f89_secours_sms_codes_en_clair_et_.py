"""secours sms codes en clair et validation manuelle garant

Revision ID: e1bc73e90f89
Revises: c7241d5ff51a
Create Date: 2026-08-30 16:53:22.264118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1bc73e90f89'
down_revision: Union[str, Sequence[str], None] = 'c7241d5ff51a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Réservé à l'administrateur : quand le fournisseur SMS échoue, il peut consulter les codes/mots
# de passe en clair pour les communiquer par un autre canal, et valider manuellement un garant
# Aide Humanitaire injoignable (cf. app/core/module_actions.py::SECOURS_SMS_GESTION).
NEW_PERMISSIONS = [
    {
        "module_action": "Secours en cas d'échec d'envoi SMS (codes en clair, validation garant manuelle)",
        "droits": {"vendeur": "aucun", "caissier": "aucun", "gerant": "aucun", "responsable_achats": "aucun", "livreur": "aucun", "administrateur": "complet"},
    },
]


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('otp_codes', sa.Column('code_clair', sa.String(length=64), nullable=True))
    op.add_column(
        'validations_garant_credit',
        sa.Column('validee_manuellement', sa.Boolean(), nullable=False, server_default=sa.false()),
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
        for ordre, ligne in enumerate(NEW_PERMISSIONS, start=103)
        for role, droit in ligne["droits"].items()
    ]
    op.bulk_insert(permissions_table, rows)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    for p in NEW_PERMISSIONS:
        conn.execute(sa.text("DELETE FROM permissions WHERE module_action = :m"), {"m": p["module_action"]})

    op.drop_column('validations_garant_credit', 'validee_manuellement')
    op.drop_column('otp_codes', 'code_clair')
