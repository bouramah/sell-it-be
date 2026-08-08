from datetime import date, datetime

from app.models.schemas import (
    Boutique,
    DroitAcces,
    Produit,
    Role,
    Secteur,
    StatutBoutique,
    StockBoutique,
    Utilisateur,
)

BOUTIQUES: list[Boutique] = [
    Boutique(
        id="btq-lansanaya",
        nom="KFSTORE Lansanaya (Siège)",
        secteurs=[Secteur.habillement, Secteur.alimentation_generale, Secteur.electronique_electromenager],
        quartier="Lansanaya",
        commune="Ratoma",
        ville="Conakry",
        adresse="Sur la déviation, Lansanaya Magasin",
        statut=StatutBoutique.active,
        responsable="Sékou Condé",
        horaires="08h00 - 20h00",
        telephone="620 19 19 20",
    ),
    Boutique(
        id="btq-matam",
        nom="KFSTORE Matam",
        secteurs=[Secteur.habillement],
        quartier="Matam Centre",
        commune="Matam",
        ville="Conakry",
        adresse="Marché de Matam",
        statut=StatutBoutique.active,
        responsable="Fatoumata Diallo",
        horaires="08h30 - 19h30",
        telephone="626 40 40 15",
    ),
    Boutique(
        id="btq-madina",
        nom="KFSTORE Madina",
        secteurs=[Secteur.alimentation_generale],
        quartier="Madina",
        commune="Matam",
        ville="Conakry",
        adresse="Grand marché de Madina",
        statut=StatutBoutique.active,
        responsable="Ibrahima Bah",
        horaires="07h00 - 21h00",
        telephone="622 11 22 33",
    ),
    Boutique(
        id="btq-kankan",
        nom="KFSTORE Kankan",
        secteurs=[Secteur.alimentation_generale, Secteur.electronique_electromenager],
        quartier="Centre-ville",
        commune="Kankan Centre",
        ville="Kankan",
        adresse="Avenue de la République",
        statut=StatutBoutique.active,
        responsable="Mamadou Camara",
        horaires="08h00 - 19h00",
        telephone="628 55 66 77",
    ),
    Boutique(
        id="btq-labe",
        nom="KFSTORE Labé",
        secteurs=[Secteur.electronique_electromenager],
        quartier="Dow Sanoyah",
        commune="Labé Centre",
        ville="Labé",
        adresse="Route de Pita",
        statut=StatutBoutique.en_creation,
        responsable="Aissatou Barry",
        horaires="—",
        telephone="623 44 55 66",
    ),
    Boutique(
        id="btq-ratoma-old",
        nom="KFSTORE Ratoma (ancien site)",
        secteurs=[Secteur.habillement],
        quartier="Ratoma",
        commune="Ratoma",
        ville="Conakry",
        adresse="Ancien marché de Ratoma",
        statut=StatutBoutique.fermee,
        responsable="—",
        horaires="—",
        telephone="—",
    ),
]

PRODUITS: list[Produit] = [
    Produit(id="prd-001", nom="Chemise homme manches longues", secteur=Secteur.habillement, categorie="Vêtements homme", prix=150000, unite="pièce", code_barres="6910000000011"),
    Produit(id="prd-002", nom="Robe wax femme", secteur=Secteur.habillement, categorie="Vêtements femme", prix=280000, unite="pièce", code_barres="6910000000028"),
    Produit(id="prd-003", nom="Riz parfumé 25kg", secteur=Secteur.alimentation_generale, categorie="Céréales", prix=320000, unite="sac", code_barres="6910000000035", date_peremption=date(2027, 3, 1)),
    Produit(id="prd-004", nom="Huile végétale 5L", secteur=Secteur.alimentation_generale, categorie="Huiles", prix=95000, unite="bidon", code_barres="6910000000042", date_peremption=date(2026, 12, 15)),
    Produit(id="prd-005", nom="Lait en poudre 900g", secteur=Secteur.alimentation_generale, categorie="Produits laitiers", prix=45000, unite="boîte", code_barres="6910000000059", date_peremption=date(2026, 9, 30)),
    Produit(id="prd-006", nom="Réfrigérateur 220L", secteur=Secteur.electronique_electromenager, categorie="Électroménager", prix=2800000, unite="pièce", code_barres="6910000000066"),
    Produit(id="prd-007", nom="Téléviseur LED 43\"", secteur=Secteur.electronique_electromenager, categorie="Électronique", prix=1950000, unite="pièce", code_barres="6910000000073"),
    Produit(id="prd-008", nom="Ventilateur sur pied", secteur=Secteur.electronique_electromenager, categorie="Électroménager", prix=380000, unite="pièce", code_barres="6910000000080"),
]

STOCKS: list[StockBoutique] = [
    StockBoutique(boutique_id="btq-lansanaya", produit_id="prd-001", quantite_disponible=42, quantite_reservee=3, seuil_alerte=15, derniere_mouvement=datetime(2026, 8, 6, 14, 20)),
    StockBoutique(boutique_id="btq-lansanaya", produit_id="prd-003", quantite_disponible=8, quantite_reservee=0, seuil_alerte=10, derniere_mouvement=datetime(2026, 8, 7, 9, 5)),
    StockBoutique(boutique_id="btq-lansanaya", produit_id="prd-006", quantite_disponible=6, quantite_reservee=1, seuil_alerte=3, derniere_mouvement=datetime(2026, 8, 5, 16, 40)),
    StockBoutique(boutique_id="btq-matam", produit_id="prd-001", quantite_disponible=18, quantite_reservee=0, seuil_alerte=15, derniere_mouvement=datetime(2026, 8, 6, 11, 0)),
    StockBoutique(boutique_id="btq-matam", produit_id="prd-002", quantite_disponible=25, quantite_reservee=2, seuil_alerte=10, derniere_mouvement=datetime(2026, 8, 7, 10, 15)),
    StockBoutique(boutique_id="btq-madina", produit_id="prd-003", quantite_disponible=54, quantite_reservee=5, seuil_alerte=20, derniere_mouvement=datetime(2026, 8, 7, 8, 30)),
    StockBoutique(boutique_id="btq-madina", produit_id="prd-004", quantite_disponible=3, quantite_reservee=0, seuil_alerte=10, derniere_mouvement=datetime(2026, 8, 4, 17, 50)),
    StockBoutique(boutique_id="btq-madina", produit_id="prd-005", quantite_disponible=12, quantite_reservee=0, seuil_alerte=15, derniere_mouvement=datetime(2026, 8, 3, 13, 10)),
    StockBoutique(boutique_id="btq-kankan", produit_id="prd-004", quantite_disponible=22, quantite_reservee=0, seuil_alerte=10, derniere_mouvement=datetime(2026, 8, 6, 9, 45)),
    StockBoutique(boutique_id="btq-kankan", produit_id="prd-007", quantite_disponible=4, quantite_reservee=1, seuil_alerte=2, derniere_mouvement=datetime(2026, 8, 2, 15, 0)),
    StockBoutique(boutique_id="btq-kankan", produit_id="prd-008", quantite_disponible=1, quantite_reservee=0, seuil_alerte=5, derniere_mouvement=datetime(2026, 8, 7, 12, 25)),
]

UTILISATEURS: list[Utilisateur] = [
    Utilisateur(id="usr-001", nom="Condé", prenom="Sékou", contact="620191920", role=Role.administrateur, boutique_ids=[b.id for b in BOUTIQUES], statut="actif", derniere_connexion=datetime(2026, 8, 8, 8, 10)),
    Utilisateur(id="usr-002", nom="Diallo", prenom="Fatoumata", contact="626404015", role=Role.gerant, boutique_ids=["btq-matam"], statut="actif", derniere_connexion=datetime(2026, 8, 8, 7, 55)),
    Utilisateur(id="usr-003", nom="Bah", prenom="Ibrahima", contact="622112233", role=Role.gerant, boutique_ids=["btq-madina"], statut="actif", derniere_connexion=datetime(2026, 8, 7, 19, 30)),
    Utilisateur(id="usr-004", nom="Camara", prenom="Mamadou", contact="628556677", role=Role.gerant, boutique_ids=["btq-kankan"], statut="actif", derniere_connexion=datetime(2026, 8, 7, 18, 5)),
    Utilisateur(id="usr-005", nom="Touré", prenom="Alpha", contact="625001122", role=Role.responsable_achats, boutique_ids=[b.id for b in BOUTIQUES], statut="actif", derniere_connexion=datetime(2026, 8, 8, 9, 0)),
    Utilisateur(id="usr-006", nom="Barry", prenom="Aissatou", contact="623445566", role=Role.caissier, boutique_ids=["btq-lansanaya"], statut="actif", derniere_connexion=datetime(2026, 8, 8, 8, 45)),
    Utilisateur(id="usr-007", nom="Sylla", prenom="Ousmane", contact="621998877", role=Role.vendeur, boutique_ids=["btq-lansanaya", "btq-matam"], statut="actif", derniere_connexion=datetime(2026, 8, 7, 20, 0)),
    Utilisateur(id="usr-008", nom="Keita", prenom="Mariam", contact="627334455", role=Role.vendeur, boutique_ids=["btq-madina"], statut="inactif", derniere_connexion=datetime(2026, 6, 12, 10, 0)),
]

# Matrice de droits reprise du CDC §3.3 (indicative, à affiner en atelier de cadrage)
PERMISSIONS: list[dict] = [
    {
        "module_action": "Consulter le stock de sa boutique",
        "droits": {Role.vendeur: DroitAcces.complet, Role.caissier: DroitAcces.complet, Role.gerant: DroitAcces.complet, Role.responsable_achats: DroitAcces.lecture_seule, Role.administrateur: DroitAcces.complet},
    },
    {
        "module_action": "Consulter le stock des autres boutiques",
        "droits": {Role.vendeur: DroitAcces.aucun, Role.caissier: DroitAcces.aucun, Role.gerant: DroitAcces.aucun, Role.responsable_achats: DroitAcces.complet, Role.administrateur: DroitAcces.complet},
    },
    {
        "module_action": "Enregistrer une vente directe (caisse)",
        "droits": {Role.vendeur: DroitAcces.complet, Role.caissier: DroitAcces.complet, Role.gerant: DroitAcces.complet, Role.responsable_achats: DroitAcces.aucun, Role.administrateur: DroitAcces.complet},
    },
    {
        "module_action": "Ouvrir / fermer une caisse",
        "droits": {Role.vendeur: DroitAcces.aucun, Role.caissier: DroitAcces.complet, Role.gerant: DroitAcces.complet, Role.responsable_achats: DroitAcces.aucun, Role.administrateur: DroitAcces.complet},
    },
    {
        "module_action": "Créer une commande fournisseur",
        "droits": {Role.vendeur: DroitAcces.aucun, Role.caissier: DroitAcces.aucun, Role.gerant: DroitAcces.partiel, Role.responsable_achats: DroitAcces.partiel, Role.administrateur: DroitAcces.complet},
    },
    {
        "module_action": "Initier un transfert de stock inter-boutiques",
        "droits": {Role.vendeur: DroitAcces.aucun, Role.caissier: DroitAcces.aucun, Role.gerant: DroitAcces.partiel, Role.responsable_achats: DroitAcces.partiel, Role.administrateur: DroitAcces.complet},
    },
    {
        "module_action": "Consulter le dashboard consolidé siège",
        "droits": {Role.vendeur: DroitAcces.aucun, Role.caissier: DroitAcces.aucun, Role.gerant: DroitAcces.aucun, Role.responsable_achats: DroitAcces.complet, Role.administrateur: DroitAcces.complet},
    },
    {
        "module_action": "Gérer les droits utilisateurs",
        "droits": {Role.vendeur: DroitAcces.aucun, Role.caissier: DroitAcces.aucun, Role.gerant: DroitAcces.aucun, Role.responsable_achats: DroitAcces.aucun, Role.administrateur: DroitAcces.complet},
    },
    {
        "module_action": "Créer / fermer une boutique",
        "droits": {Role.vendeur: DroitAcces.aucun, Role.caissier: DroitAcces.aucun, Role.gerant: DroitAcces.aucun, Role.responsable_achats: DroitAcces.aucun, Role.administrateur: DroitAcces.complet},
    },
    {
        "module_action": "Accéder aux modules IA (reco, prévisions, chatbot config)",
        "droits": {Role.vendeur: DroitAcces.aucun, Role.caissier: DroitAcces.aucun, Role.gerant: DroitAcces.lecture_seule, Role.responsable_achats: DroitAcces.complet, Role.administrateur: DroitAcces.complet},
    },
]
