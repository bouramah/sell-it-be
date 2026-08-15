"""add parametres_application table (mode hors-ligne)

Revision ID: 34578ac2f55e
Revises: 1b08d83a2d0a
Create Date: 2026-08-15 01:09:28.020066

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '34578ac2f55e'
down_revision: Union[str, Sequence[str], None] = '1b08d83a2d0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PARAMETRES_APPLICATION = [
    {
        "id": "mode_hors_ligne",
        "label": "Mode hors-ligne — caisse et stock (appli mobile interne)",
        "actif": True,
        "ordre": 0,
    },
]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'parametres_application',
        sa.Column('id', sa.String(length=60), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('actif', sa.Boolean(), nullable=False),
        sa.Column('ordre', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(length=160), nullable=True),
        sa.Column('updated_by', sa.String(length=160), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    table = sa.table(
        'parametres_application',
        sa.column('id', sa.String),
        sa.column('label', sa.String),
        sa.column('actif', sa.Boolean),
        sa.column('ordre', sa.Integer),
    )
    op.bulk_insert(table, PARAMETRES_APPLICATION)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('parametres_application')
