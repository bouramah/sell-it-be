"""généralise aide enseignants vers aide humanitaire (etablissements/beneficiaires, poste,
type_etablissement, numero_membre)

Revision ID: d642c0cae6e8
Revises: c5f2a8d19e04
Create Date: 2026-08-27 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd642c0cae6e8'
down_revision: Union[str, Sequence[str], None] = 'c5f2a8d19e04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Le module « Aide aux Enseignants » (école/enseignant) est généralisé en « Aide Humanitaire »
# (établissement/bénéficiaire) : n'importe quel établissement partenaire — école, établissement
# de santé, entreprise, ou autre structure — peut désormais parrainer ses salariés. RENAME TABLE
# sous MySQL/MariaDB met à jour automatiquement les FK qui pointent vers la table renommée ; un
# CHANGE COLUMN (ce que génère alter_column(new_column_name=...) sous ce dialecte) préserve de la
# même façon la FK portée par la colonne renommée.

RENOMMAGE_PERMISSIONS = [
    ("Gérer les écoles partenaires et leurs garants", "Gérer les établissements partenaires et leurs garants"),
    ("Gérer les enseignants bénéficiaires (aide aux enseignants)", "Gérer les bénéficiaires (aide humanitaire)"),
    ("Paramétrer le barème de plafond de crédit enseignants", "Paramétrer le barème de plafond de crédit aide humanitaire"),
]

TYPES_ETABLISSEMENT = [
    ("education", "Éducation"),
    ("sante", "Santé"),
    ("entreprise", "Entreprise"),
    ("autre", "Autre"),
]


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table('ecoles', 'etablissements')
    op.add_column('etablissements', sa.Column('type_etablissement', sa.String(length=60), nullable=False))

    op.rename_table('enseignants', 'beneficiaires')
    op.alter_column('beneficiaires', 'ecole_id', new_column_name='etablissement_id', existing_type=sa.String(length=40), nullable=False)
    op.alter_column('beneficiaires', 'grade_echelon', new_column_name='poste', existing_type=sa.String(length=120), nullable=False)
    op.add_column('beneficiaires', sa.Column('numero_membre', sa.String(length=20), nullable=False))
    op.create_unique_constraint('uq_beneficiaires_numero_membre', 'beneficiaires', ['numero_membre'])

    op.rename_table('baremes_credit_enseignants', 'baremes_credit_beneficiaires')
    op.alter_column('baremes_credit_beneficiaires', 'ecole_id', new_column_name='etablissement_id', existing_type=sa.String(length=40), nullable=True)
    op.alter_column('baremes_credit_beneficiaires', 'grade_echelon', new_column_name='poste', existing_type=sa.String(length=120), nullable=False)

    op.rename_table('versements_ecoles', 'versements_etablissements')
    op.alter_column('versements_etablissements', 'ecole_id', new_column_name='etablissement_id', existing_type=sa.String(length=40), nullable=False)

    referentiels_table = sa.table(
        'referentiels',
        sa.column('id', sa.String),
        sa.column('categorie', sa.String),
        sa.column('nom', sa.String),
    )
    op.bulk_insert(referentiels_table, [
        {"id": item_id, "categorie": "types_etablissement", "nom": nom} for item_id, nom in TYPES_ETABLISSEMENT
    ])

    conn = op.get_bind()
    for ancien, nouveau in RENOMMAGE_PERMISSIONS:
        conn.execute(sa.text("UPDATE permissions SET module_action = :nouveau WHERE module_action = :ancien"), {"nouveau": nouveau, "ancien": ancien})


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    for ancien, nouveau in RENOMMAGE_PERMISSIONS:
        conn.execute(sa.text("UPDATE permissions SET module_action = :ancien WHERE module_action = :nouveau"), {"nouveau": nouveau, "ancien": ancien})

    conn.execute(sa.text("DELETE FROM referentiels WHERE categorie = 'types_etablissement'"))

    op.alter_column('versements_etablissements', 'etablissement_id', new_column_name='ecole_id', existing_type=sa.String(length=40), nullable=False)
    op.rename_table('versements_etablissements', 'versements_ecoles')

    op.alter_column('baremes_credit_beneficiaires', 'poste', new_column_name='grade_echelon', existing_type=sa.String(length=120), nullable=False)
    op.alter_column('baremes_credit_beneficiaires', 'etablissement_id', new_column_name='ecole_id', existing_type=sa.String(length=40), nullable=True)
    op.rename_table('baremes_credit_beneficiaires', 'baremes_credit_enseignants')

    op.drop_constraint('uq_beneficiaires_numero_membre', 'beneficiaires', type_='unique')
    op.drop_column('beneficiaires', 'numero_membre')
    op.alter_column('beneficiaires', 'poste', new_column_name='grade_echelon', existing_type=sa.String(length=120), nullable=False)
    op.alter_column('beneficiaires', 'etablissement_id', new_column_name='ecole_id', existing_type=sa.String(length=40), nullable=False)
    op.rename_table('beneficiaires', 'enseignants')

    op.drop_column('etablissements', 'type_etablissement')
    op.rename_table('etablissements', 'ecoles')
