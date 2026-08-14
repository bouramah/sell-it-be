"""seed livreur role and permissions

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-15 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Le rôle "livreur" est référencé en dur côté appli mobile (navigation dédiée,
# écran "Mes livraisons") depuis le début du projet, mais n'a jamais été semé en
# base — la table roles/permissions ne connaissait que les 5 rôles du CDC
# (vendeur/caissier/gérant/responsable_achats/administrateur). Sans cette ligne,
# créer un utilisateur "livreur" échoue (FK role -> roles.id inexistante) : le
# profil livreur était jusqu'ici impossible à tester ou utiliser réellement.
LIVREUR_PERMISSIONS = [
    ('Consulter le stock de sa boutique', 'aucun', 0),
    ('Consulter le stock des autres boutiques', 'aucun', 1),
    ('Enregistrer une vente directe (caisse)', 'aucun', 2),
    ('Ouvrir / fermer une caisse', 'aucun', 3),
    ('Créer une commande fournisseur', 'aucun', 4),
    ("Valider les dépenses au-delà d'un seuil", 'aucun', 6),
    ('Consulter le dashboard consolidé siège', 'aucun', 7),
    ('Gérer les droits utilisateurs', 'aucun', 8),
    ('Créer / fermer une boutique', 'aucun', 9),
    ('Valider un encaissement / paiement', 'aucun', 10),
    ('Créer / modifier une commande client', 'aucun', 11),
    ('Enregistrer une dette / créance client', 'aucun', 12),
    ('Enregistrer un remboursement de dette', 'aucun', 13),
    ('Réceptionner un transfert de stock', 'aucun', 14),
    ('Gérer les livraisons (affectation livreur, suivi)', 'complet', 15),
    ('Enregistrer une dépense de boutique', 'aucun', 16),
    ('Consulter le dashboard de sa boutique', 'aucun', 17),
    ('Consulter la vue globale des mouvements de caisse/stock', 'aucun', 18),
    ('Consulter la comptabilité de sa boutique', 'aucun', 19),
    ('Consulter la comptabilité consolidée du réseau', 'aucun', 20),
    ('Paramétrer les promotions et tarifs', 'aucun', 21),
    ('Accéder aux modules IA', 'aucun', 22),
    ('Gérer le catalogue produits (créer/modifier/supprimer)', 'aucun', 23),
    ('Gérer les fournisseurs (créer/modifier/supprimer)', 'aucun', 24),
    ('Créer / modifier une fiche client', 'aucun', 25),
    ('Initier un transfert de stock (demande)', 'aucun', 26),
    ("Valider un transfert de stock (autoriser l'envoi)", 'aucun', 27),
    ('Réceptionner une commande fournisseur', 'aucun', 28),
    ('Valider ou refuser une promotion', 'aucun', 29),
    ('Modifier le stock (ajout de ligne, mouvement manuel, inventaire)', 'aucun', 30),
    ('Gérer les référentiels (villes, catégories, motifs…)', 'aucun', 31),
    ("Consulter le journal d'audit et gérer les paramètres de sécurité", 'aucun', 32),
    ('Enregistrer un mouvement de caisse manuel', 'aucun', 33),
    ('Valider une remise au-delà du seuil', 'aucun', 34),
]


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    roles_table = sa.table(
        'roles',
        sa.column('id', sa.String), sa.column('libelle', sa.String),
        sa.column('portee', sa.String), sa.column('ordre', sa.Integer), sa.column('systeme', sa.Boolean),
    )
    conn.execute(roles_table.insert(), [
        {'id': 'livreur', 'libelle': 'Livreur', 'portee': 'boutique', 'ordre': 5, 'systeme': True},
    ])

    permissions_table = sa.table(
        'permissions',
        sa.column('module_action', sa.String), sa.column('role', sa.String),
        sa.column('droit', sa.String), sa.column('ordre', sa.Integer),
    )
    conn.execute(permissions_table.insert(), [
        {'module_action': module_action, 'role': 'livreur', 'droit': droit, 'ordre': ordre}
        for module_action, droit, ordre in LIVREUR_PERMISSIONS
    ])


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM permissions WHERE role = 'livreur'")
    op.execute("DELETE FROM roles WHERE id = 'livreur'")
