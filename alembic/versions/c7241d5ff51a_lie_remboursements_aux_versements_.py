"""lie remboursements aux versements etablissement

Revision ID: c7241d5ff51a
Revises: d642c0cae6e8
Create Date: 2026-08-29 17:52:27.490725

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7241d5ff51a'
down_revision: Union[str, Sequence[str], None] = 'd642c0cae6e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('remboursements', sa.Column('versement_etablissement_id', sa.String(length=40), nullable=True))
    op.create_foreign_key(
        'fk_remboursements_versement_etablissement_id', 'remboursements', 'versements_etablissements',
        ['versement_etablissement_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_remboursements_versement_etablissement_id', 'remboursements', type_='foreignkey')
    op.drop_column('remboursements', 'versement_etablissement_id')
