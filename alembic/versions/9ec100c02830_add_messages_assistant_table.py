"""add messages_assistant table

Revision ID: 9ec100c02830
Revises: ba14e9456284
Create Date: 2026-08-18 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9ec100c02830'
down_revision: Union[str, Sequence[str], None] = 'ba14e9456284'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'messages_assistant',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('client_id', sa.String(length=40), nullable=False),
        sa.Column('auteur', sa.String(length=10), nullable=False),
        sa.Column('texte', sa.Text(), nullable=False),
        sa.Column('horodatage', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_messages_assistant_client_id'), 'messages_assistant', ['client_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_messages_assistant_client_id'), table_name='messages_assistant')
    op.drop_table('messages_assistant')
