"""make journal_audit boutique_id fk set null on boutique delete

Revision ID: eee5fd6ddec1
Revises: 5f35f9d08c80
Create Date: 2026-08-11 15:36:56.772711

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eee5fd6ddec1'
down_revision: Union[str, Sequence[str], None] = '5f35f9d08c80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("journal_audit") as batch_op:
        batch_op.drop_constraint("journal_audit_ibfk_1", type_="foreignkey")
        batch_op.create_foreign_key(
            "journal_audit_ibfk_1", "boutiques", ["boutique_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("journal_audit") as batch_op:
        batch_op.drop_constraint("journal_audit_ibfk_1", type_="foreignkey")
        batch_op.create_foreign_key(
            "journal_audit_ibfk_1", "boutiques", ["boutique_id"], ["id"]
        )
