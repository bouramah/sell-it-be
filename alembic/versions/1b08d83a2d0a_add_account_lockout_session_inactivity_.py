"""add account lockout, session inactivity, otp objectif and audit before/after

Revision ID: 1b08d83a2d0a
Revises: d4e5f6a7b8c9
Create Date: 2026-08-15 00:00:41.359532

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1b08d83a2d0a'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('journal_audit', sa.Column('valeur_avant', sa.Text(), nullable=True))
    op.add_column('journal_audit', sa.Column('valeur_apres', sa.Text(), nullable=True))

    # server_default pour satisfaire les lignes existantes (codes OTP déjà émis, tous pour
    # la réinitialisation de mot de passe avant l'introduction de la 2FA à la connexion).
    op.add_column('otp_codes', sa.Column('objectif', sa.String(length=20), nullable=False, server_default='reinitialisation'))
    op.alter_column('otp_codes', 'objectif', server_default=None)

    op.add_column('utilisateurs', sa.Column('tentatives_echouees', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('utilisateurs', 'tentatives_echouees', server_default=None)
    op.add_column('utilisateurs', sa.Column('verrouille_jusqua', sa.DateTime(), nullable=True))
    op.add_column('utilisateurs', sa.Column('derniere_activite', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('utilisateurs', 'derniere_activite')
    op.drop_column('utilisateurs', 'verrouille_jusqua')
    op.drop_column('utilisateurs', 'tentatives_echouees')
    op.drop_column('otp_codes', 'objectif')
    op.drop_column('journal_audit', 'valeur_apres')
    op.drop_column('journal_audit', 'valeur_avant')
