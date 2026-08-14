"""add created_at updated_at created_by updated_by audit columns

Revision ID: d1b95cf72cda
Revises: 1ffc630300b6
Create Date: 2026-08-14 03:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1b95cf72cda'
down_revision: Union[str, Sequence[str], None] = '1ffc630300b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Traçabilité systématique (qui/quand a créé/modifié chaque enregistrement) — décision produit
# du 2026-08-14. Appliquée à toutes les tables sauf : boutique_secteurs (jonction pure, sans
# identité propre), prix_periodes/prix_achats (portent déjà cree_le/modifie_par équivalents),
# journal_audit (déjà horodatage/auteur, journal immuable).

TABLES = [
    "boutiques", "roles", "utilisateurs", "produits", "produit_images", "referentiels",
    "fournisseurs", "regions", "villes", "communes", "quartiers_geo", "secteurs_geo", "clients",
    "stock_boutiques", "mouvements_stock", "ecarts_inventaire", "caisses", "mouvements_caisse",
    "commandes_clients", "lignes_commandes_clients", "commandes_fournisseurs",
    "lignes_commandes_fournisseurs", "dettes", "remboursements", "transferts_stock", "livraisons",
    "depenses", "paiements_clients", "paiements_fournisseurs", "permissions", "promotions",
    "parametres_securite", "otp_codes",
]


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        # otp_codes porte déjà son propre created_at (géré par l'appli, sans lien avec ce
        # mixin) — AuditMixin ne l'y redéclare pas, donc ne pas l'ajouter ici non plus.
        if table != "otp_codes":
            op.add_column(table, sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True))
        op.add_column(table, sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True))
        op.add_column(table, sa.Column("created_by", sa.String(length=160), nullable=True))
        op.add_column(table, sa.Column("updated_by", sa.String(length=160), nullable=True))
    # MySQL/MariaDB : ON UPDATE CURRENT_TIMESTAMP ne se déclare pas via un simple server_default,
    # il faut l'ALTER dédié pour que updated_at se mette réellement à jour tout seul en base.
    conn = op.get_bind()
    for table in TABLES:
        conn.execute(sa.text(
            f"ALTER TABLE {table} MODIFY updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        ))


def downgrade() -> None:
    """Downgrade schema."""
    for table in TABLES:
        op.drop_column(table, "updated_by")
        op.drop_column(table, "created_by")
        op.drop_column(table, "updated_at")
        op.drop_column(table, "created_at")
