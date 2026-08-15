"""add client mobile app: client_id FKs, unique client contact, demandes_credit table

Revision ID: 571364292b67
Revises: 34578ac2f55e
Create Date: 2026-08-15 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '571364292b67'
down_revision: Union[str, Sequence[str], None] = '34578ac2f55e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'demandes_credit',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('client_id', sa.String(length=40), nullable=False),
        sa.Column('boutique_id', sa.String(length=40), nullable=False),
        sa.Column('montant_souhaite', sa.Float(), nullable=False),
        sa.Column('motif', sa.String(length=255), nullable=False),
        sa.Column('statut', sa.Enum('en_attente', 'validee', 'refusee', name='statutdemandecredit'), nullable=False),
        sa.Column('date_creation', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=160), nullable=True),
        sa.Column('updated_by', sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(['boutique_id'], ['boutiques.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(op.f('ix_clients_contact'), 'clients', ['contact'], unique=True)

    op.add_column('commandes_clients', sa.Column('client_id', sa.String(length=40), nullable=True))
    op.create_foreign_key('fk_commandes_clients_client_id', 'commandes_clients', 'clients', ['client_id'], ['id'], ondelete='SET NULL')

    op.add_column('dettes', sa.Column('client_id', sa.String(length=40), nullable=True))
    op.create_foreign_key('fk_dettes_client_id', 'dettes', 'clients', ['client_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_dettes_client_id', 'dettes', type_='foreignkey')
    op.drop_column('dettes', 'client_id')

    op.drop_constraint('fk_commandes_clients_client_id', 'commandes_clients', type_='foreignkey')
    op.drop_column('commandes_clients', 'client_id')

    op.drop_index(op.f('ix_clients_contact'), table_name='clients')

    op.drop_table('demandes_credit')
