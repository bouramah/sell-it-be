"""expand journal_audit for automatic per-request tracing

Revision ID: d27d62f2a7d3
Revises: 571364292b67
Create Date: 2026-08-16 20:22:46.483990

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd27d62f2a7d3'
down_revision: Union[str, Sequence[str], None] = '571364292b67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('journal_audit', sa.Column('utilisateur_id', sa.String(length=40), nullable=True))
    op.add_column('journal_audit', sa.Column('client_id', sa.String(length=40), nullable=True))
    op.add_column('journal_audit', sa.Column('canal', sa.String(length=20), nullable=True))
    op.add_column('journal_audit', sa.Column('methode', sa.String(length=10), nullable=True))
    op.add_column('journal_audit', sa.Column('chemin', sa.String(length=255), nullable=True))
    op.add_column('journal_audit', sa.Column('statut_code', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_journal_audit_utilisateur_id', 'journal_audit', 'utilisateurs',
        ['utilisateur_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_journal_audit_client_id', 'journal_audit', 'clients',
        ['client_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_journal_audit_horodatage', 'journal_audit', ['horodatage'])
    op.create_index('ix_journal_audit_utilisateur_id', 'journal_audit', ['utilisateur_id'])
    op.create_index('ix_journal_audit_client_id', 'journal_audit', ['client_id'])
    op.create_index('ix_journal_audit_canal', 'journal_audit', ['canal'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_journal_audit_canal', table_name='journal_audit')
    op.drop_index('ix_journal_audit_client_id', table_name='journal_audit')
    op.drop_index('ix_journal_audit_utilisateur_id', table_name='journal_audit')
    op.drop_index('ix_journal_audit_horodatage', table_name='journal_audit')
    op.drop_constraint('fk_journal_audit_client_id', 'journal_audit', type_='foreignkey')
    op.drop_constraint('fk_journal_audit_utilisateur_id', 'journal_audit', type_='foreignkey')
    op.drop_column('journal_audit', 'statut_code')
    op.drop_column('journal_audit', 'chemin')
    op.drop_column('journal_audit', 'methode')
    op.drop_column('journal_audit', 'canal')
    op.drop_column('journal_audit', 'client_id')
    op.drop_column('journal_audit', 'utilisateur_id')
