"""code-barres produit facultatif

Revision ID: 6416118ce96c
Revises: a4a82363000f
Create Date: 2026-10-05 18:48:42.383642

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '6416118ce96c'
down_revision: Union[str, Sequence[str], None] = 'a4a82363000f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('produits', 'code_barres',
               existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=40),
               nullable=True)


def downgrade() -> None:
    op.alter_column('produits', 'code_barres',
               existing_type=mysql.VARCHAR(collation='utf8mb4_unicode_ci', length=40),
               nullable=False)
