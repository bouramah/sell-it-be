"""add aide enseignants tables (ecoles, enseignants, bareme, validations garant, versements)

Revision ID: b3e7c1f4a982
Revises: c9d4f5a61b27
Create Date: 2026-08-27 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3e7c1f4a982'
down_revision: Union[str, Sequence[str], None] = 'c9d4f5a61b27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.String(length=160), nullable=True),
        sa.Column('updated_by', sa.String(length=160), nullable=True),
    ]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ecoles',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('nom', sa.String(length=160), nullable=False),
        sa.Column('adresse', sa.String(length=255), nullable=True),
        sa.Column('referent_nom', sa.String(length=160), nullable=False),
        sa.Column('referent_contact', sa.String(length=40), nullable=False),
        sa.Column('comptabilite_nom', sa.String(length=160), nullable=False),
        sa.Column('comptabilite_contact', sa.String(length=40), nullable=False),
        sa.Column('statut', sa.Enum('active', 'inactive', name='statutecole'), nullable=False),
        *_audit_columns(),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'enseignants',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('client_id', sa.String(length=40), nullable=False),
        sa.Column('ecole_id', sa.String(length=40), nullable=False),
        sa.Column('grade_echelon', sa.String(length=120), nullable=False),
        sa.Column('salaire_reference', sa.Float(), nullable=False),
        sa.Column('engagement_signe_url', sa.String(length=500), nullable=True),
        sa.Column('engagement_signe_date', sa.Date(), nullable=True),
        sa.Column('plafond_suspendu', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ecole_id'], ['ecoles.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id'),
    )

    op.create_table(
        'baremes_credit_enseignants',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('ecole_id', sa.String(length=40), nullable=True),
        sa.Column('grade_echelon', sa.String(length=120), nullable=False),
        sa.Column('plafond', sa.Float(), nullable=False),
        sa.Column('date_debut', sa.Date(), nullable=False),
        sa.Column('date_fin', sa.Date(), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['ecole_id'], ['ecoles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'validations_garant_credit',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('demande_credit_id', sa.String(length=40), nullable=False),
        sa.Column('type_garant', sa.Enum('referent', 'comptabilite', name='typegarant'), nullable=False),
        sa.Column('nom_garant', sa.String(length=160), nullable=False),
        sa.Column('contact_garant', sa.String(length=40), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('statut', sa.Enum('en_attente', 'validee', 'refusee', name='statutvalidationgarant'), nullable=False),
        sa.Column('date_reponse', sa.DateTime(), nullable=True),
        sa.Column('motif_refus', sa.String(length=255), nullable=True),
        sa.Column('expire_le', sa.DateTime(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['demande_credit_id'], ['demandes_credit.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index('ix_validations_garant_credit_token', 'validations_garant_credit', ['token'], unique=True)

    op.create_table(
        'versements_ecoles',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('ecole_id', sa.String(length=40), nullable=False),
        sa.Column('montant', sa.Float(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('reference', sa.String(length=160), nullable=True),
        sa.Column('justificatif_url', sa.String(length=500), nullable=True),
        sa.Column('note', sa.String(length=255), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(['ecole_id'], ['ecoles.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column('dettes', sa.Column('demande_credit_id', sa.String(length=40), nullable=True))
    op.create_foreign_key(
        'fk_dettes_demande_credit_id', 'dettes', 'demandes_credit', ['demande_credit_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_dettes_demande_credit_id', 'dettes', type_='foreignkey')
    op.drop_column('dettes', 'demande_credit_id')
    op.drop_table('versements_ecoles')
    op.drop_index('ix_validations_garant_credit_token', table_name='validations_garant_credit')
    op.drop_table('validations_garant_credit')
    op.drop_table('baremes_credit_enseignants')
    op.drop_table('enseignants')
    op.drop_table('ecoles')
