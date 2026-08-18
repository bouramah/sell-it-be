"""seed chatbot_actif parametre application

Revision ID: ba14e9456284
Revises: d27d62f2a7d3
Create Date: 2026-08-17 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ba14e9456284'
down_revision: Union[str, Sequence[str], None] = 'd27d62f2a7d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    table = sa.table(
        'parametres_application',
        sa.column('id', sa.String),
        sa.column('label', sa.String),
        sa.column('actif', sa.Boolean),
        sa.column('ordre', sa.Integer),
    )
    op.bulk_insert(table, [{
        "id": "chatbot_actif",
        "label": "Assistant IA — chatbot service client (appli mobile client)",
        "actif": True,
        "ordre": 1,
    }])


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM parametres_application WHERE id = 'chatbot_actif'")
