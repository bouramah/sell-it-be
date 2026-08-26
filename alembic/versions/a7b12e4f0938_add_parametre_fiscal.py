"""add parametres_fiscaux table (taux TVA configurable)

Revision ID: a7b12e4f0938
Revises: f3a8c1d02e91
Create Date: 2026-08-26 21:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7b12e4f0938'
down_revision: Union[str, Sequence[str], None] = 'f3a8c1d02e91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'parametres_fiscaux',
        sa.Column('id', sa.String(length=60), nullable=False),
        sa.Column('taux', sa.Float(), nullable=False),
        sa.Column('actif', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.String(length=160), nullable=True),
        sa.Column('updated_by', sa.String(length=160), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.execute(
        "INSERT INTO parametres_fiscaux (id, taux, actif, created_by, updated_by) "
        "VALUES ('tva', 0.18, 1, 'Migration', 'Migration')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('parametres_fiscaux')
