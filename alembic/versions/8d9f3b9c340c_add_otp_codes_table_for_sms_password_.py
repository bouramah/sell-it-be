"""add otp_codes table for sms password reset

Revision ID: 8d9f3b9c340c
Revises: eee5fd6ddec1
Create Date: 2026-08-11 15:51:27.112958

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d9f3b9c340c'
down_revision: Union[str, Sequence[str], None] = 'eee5fd6ddec1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "otp_codes",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("contact", sa.String(30), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_otp_codes_contact", "otp_codes", ["contact"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_otp_codes_contact", table_name="otp_codes")
    op.drop_table("otp_codes")
