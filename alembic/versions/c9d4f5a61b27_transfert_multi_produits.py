"""transfert stock : passage à un modèle en-tête + lignes (multi-produits)

Revision ID: c9d4f5a61b27
Revises: a7b12e4f0938
Create Date: 2026-08-26 22:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c9d4f5a61b27'
down_revision: Union[str, Sequence[str], None] = 'a7b12e4f0938'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'lignes_transferts_stock',
        sa.Column('id', sa.String(length=40), nullable=False),
        sa.Column('transfert_id', sa.String(length=40), nullable=False),
        sa.Column('produit_id', sa.String(length=40), nullable=False),
        sa.Column('quantite', sa.Integer(), nullable=False),
        sa.Column('quantite_recue', sa.Integer(), nullable=True),
        sa.Column('motif_ecart', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.String(length=160), nullable=True),
        sa.Column('updated_by', sa.String(length=160), nullable=True),
        sa.ForeignKeyConstraint(['transfert_id'], ['transferts_stock.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['produit_id'], ['produits.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    connexion = op.get_bind()
    existants = connexion.execute(sa.text(
        "SELECT id, produit_id, quantite, quantite_recue, motif_ecart, created_by, updated_by "
        "FROM transferts_stock"
    )).fetchall()
    for row in existants:
        connexion.execute(
            sa.text(
                "INSERT INTO lignes_transferts_stock "
                "(id, transfert_id, produit_id, quantite, quantite_recue, motif_ecart, created_by, updated_by) "
                "VALUES (:id, :transfert_id, :produit_id, :quantite, :quantite_recue, :motif_ecart, :created_by, :updated_by)"
            ),
            {
                "id": str(uuid.uuid4())[:8], "transfert_id": row.id, "produit_id": row.produit_id,
                "quantite": row.quantite, "quantite_recue": row.quantite_recue, "motif_ecart": row.motif_ecart,
                "created_by": row.created_by, "updated_by": row.updated_by,
            },
        )

    with op.batch_alter_table('transferts_stock') as batch:
        batch.drop_constraint('transferts_stock_ibfk_3', type_='foreignkey')
        batch.drop_column('produit_id')
        batch.drop_column('quantite')
        batch.drop_column('quantite_recue')
        batch.drop_column('motif_ecart')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('transferts_stock') as batch:
        batch.add_column(sa.Column('produit_id', sa.String(length=40), nullable=True))
        batch.add_column(sa.Column('quantite', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('quantite_recue', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('motif_ecart', sa.String(length=255), nullable=True))

    connexion = op.get_bind()
    premieres_lignes = connexion.execute(sa.text(
        "SELECT transfert_id, produit_id, quantite, quantite_recue, motif_ecart FROM lignes_transferts_stock"
    )).fetchall()
    for row in premieres_lignes:
        connexion.execute(
            sa.text(
                "UPDATE transferts_stock SET produit_id = :produit_id, quantite = :quantite, "
                "quantite_recue = :quantite_recue, motif_ecart = :motif_ecart WHERE id = :transfert_id"
            ),
            {
                "produit_id": row.produit_id, "quantite": row.quantite,
                "quantite_recue": row.quantite_recue, "motif_ecart": row.motif_ecart, "transfert_id": row.transfert_id,
            },
        )

    op.drop_table('lignes_transferts_stock')
    with op.batch_alter_table('transferts_stock') as batch:
        batch.alter_column('produit_id', nullable=False)
        batch.alter_column('quantite', nullable=False)
        batch.create_foreign_key('transferts_stock_ibfk_1', 'produits', ['produit_id'], ['id'])
