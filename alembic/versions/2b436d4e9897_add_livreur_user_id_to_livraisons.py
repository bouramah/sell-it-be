"""add livreur_user_id to livraisons

Revision ID: 2b436d4e9897
Revises: 69c7f880a599
Create Date: 2026-08-12 12:35:08.017354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b436d4e9897'
down_revision: Union[str, Sequence[str], None] = '69c7f880a599'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('livraisons', sa.Column('livreur_user_id', sa.String(length=40), nullable=True))
    op.create_foreign_key('fk_livraisons_livreur_user_id', 'livraisons', 'utilisateurs', ['livreur_user_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_livraisons_livreur_user_id', 'livraisons', type_='foreignkey')
    op.drop_column('livraisons', 'livreur_user_id')
