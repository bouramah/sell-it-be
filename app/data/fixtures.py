from datetime import date, datetime

from app.models.schemas import (
    AnomalieReporting,
    Boutique,
    Caisse,
    Client,
    CommandeClient,
    Depense,
    Dette,
    EcartInventaire,
    Fournisseur,
    JournalAuditEntry,
    LigneCommandeFournisseur,
    Livraison,
    MotifMouvementStock,
    MouvementCaisse,
    MouvementStock,
    PaiementClient,
    PaiementFournisseur,
    ParametreSecurite,
    Produit,
    Promotion,
    ReferentielItem,
    Remboursement,
    Role,
    StatutBoutique,
    StatutCaisse,
    StatutCommandeClient,
    StatutCommandeFournisseur,
    StatutDette,
    StatutLivraison,
    StatutPaiement,
    StatutPromotion,
    StatutTransfert,
    StatutValidationDepense,
    StockBoutique,
    SuggestionReapprovisionnement,
    TiersType,
    TransfertStock,
    TypeMouvementCaisse,
    Utilisateur,
)

# --- Réseau ------------------------------------------------------------------

BOUTIQUES: list[Boutique] = [
    Boutique(
        id="lansanaya",
        nom="Lansanaya (siège)",
        secteurs=["habillement", "alimentation_generale", "electronique_electromenager"],
        quartier="Lansanaya",
        commune="Ratoma",
        ville="Conakry",
        horaires="08h00 – 20h00, tous les jours",
        responsable="Fatoumata Bah",
        statut=StatutBoutique.active,
        telephone="620 19 19 20",
    ),
    Boutique(
        id="madina",
        nom="Madina",
        secteurs=["alimentation_generale"],
        quartier="Madina",
        commune="Kaloum",
        ville="Conakry",
        horaires="07h30 – 19h30, tous les jours",
        responsable="Ibrahima Sow",
        statut=StatutBoutique.active,
        telephone="622 11 22 33",
    ),
    Boutique(
        id="matam",
        nom="Matam",
        secteurs=["electronique_electromenager"],
        quartier="Matam",
        commune="Matoto",
        ville="Conakry",
        horaires="08h30 – 19h00, tous les jours",
        responsable="Alpha Camara",
        statut=StatutBoutique.active,
        telephone="628 55 66 77",
    ),
    Boutique(
        id="kaloum",
        nom="Kaloum",
        secteurs=["habillement"],
        quartier="Kaloum centre",
        commune="Kaloum",
        ville="Conakry",
        horaires="08h00 – 19h00, tous les jours",
        responsable="Aboubacar Diané",
        statut=StatutBoutique.active,
        telephone="620 77 88 99",
    ),
    Boutique(
        id="kankan",
        nom="Kankan",
        secteurs=["alimentation_generale"],
        quartier="Centre-ville",
        commune="Kankan Centre",
        ville="Kankan",
        horaires="—",
        responsable="Mariama Diallo",
        statut=StatutBoutique.en_creation,
        telephone="623 44 55 66",
    ),
]

FOURNISSEURS: list[Fournisseur] = [
    Fournisseur(id="sotramag", nom="Sotramag Import", secteur="alimentation_generale", conditions_paiement="30 jours, virement/mobile money", contact="628 00 11 22"),
    Fournisseur(id="guinee-textiles", nom="Guinée Textiles", secteur="habillement", conditions_paiement="Comptant à la livraison", contact="622 45 90 10"),
    Fournisseur(id="africa-electro", nom="Africa Electro", secteur="electronique_electromenager", conditions_paiement="45 jours, lettre de change", contact="655 30 20 40"),
    Fournisseur(id="grossiste-kaloum", nom="Grossiste Kaloum", secteur="habillement", conditions_paiement="Comptant", contact="620 77 88 99"),
]

UTILISATEURS: list[Utilisateur] = [
    Utilisateur(id="usr-condé", nom="Condé", prenom="Sékou", contact="620191920", role=Role.administrateur, boutique_ids=[b.id for b in BOUTIQUES], statut="actif", derniere_connexion=datetime(2026, 8, 8, 11, 2)),
    Utilisateur(id="usr-bah-f", nom="Bah", prenom="Fatoumata", contact="620000001", role=Role.gerant, boutique_ids=["lansanaya"], statut="actif", derniere_connexion=datetime(2026, 8, 8, 8, 12)),
    Utilisateur(id="usr-sow", nom="Sow", prenom="Ibrahima", contact="622112233", role=Role.gerant, boutique_ids=["madina"], statut="actif", derniere_connexion=datetime(2026, 8, 8, 7, 58)),
    Utilisateur(id="usr-camara", nom="Camara", prenom="Alpha", contact="628556677", role=Role.gerant, boutique_ids=["matam"], statut="actif", derniere_connexion=datetime(2026, 8, 8, 9, 5)),
    Utilisateur(id="usr-diane", nom="Diané", prenom="Aboubacar", contact="620778899", role=Role.gerant, boutique_ids=["kaloum"], statut="actif", derniere_connexion=datetime(2026, 8, 7, 20, 30)),
    Utilisateur(id="usr-diallo", nom="Diallo", prenom="Mariama", contact="623445566", role=Role.caissier, boutique_ids=["kankan"], statut="actif", derniere_connexion=datetime(2026, 8, 7, 18, 40)),
    Utilisateur(id="usr-keita", nom="Keita", prenom="Mamadouba", contact="625001122", role=Role.responsable_achats, boutique_ids=[b.id for b in BOUTIQUES], statut="actif", derniere_connexion=datetime(2026, 8, 8, 10, 20)),
    Utilisateur(id="usr-bah-s", nom="Bah", prenom="Souleymane", contact="621998877", role=Role.vendeur, boutique_ids=["kaloum"], statut="inactif", derniere_connexion=datetime(2026, 7, 7, 9, 47)),
]

PERMISSIONS: list[dict] = [
    {"module_action": "Consulter le stock de sa boutique", "droits": {Role.vendeur: "complet", Role.caissier: "complet", Role.gerant: "complet", Role.responsable_achats: "complet", Role.administrateur: "complet"}},
    {"module_action": "Consulter le stock des autres boutiques", "droits": {Role.vendeur: "aucun", Role.caissier: "aucun", Role.gerant: "aucun", Role.responsable_achats: "complet", Role.administrateur: "complet"}},
    {"module_action": "Enregistrer une vente directe (caisse)", "droits": {Role.vendeur: "complet", Role.caissier: "complet", Role.gerant: "complet", Role.responsable_achats: "aucun", Role.administrateur: "complet"}},
    {"module_action": "Ouvrir / fermer une caisse", "droits": {Role.vendeur: "aucun", Role.caissier: "complet", Role.gerant: "complet", Role.responsable_achats: "aucun", Role.administrateur: "complet"}},
    {"module_action": "Créer une commande fournisseur", "droits": {Role.vendeur: "aucun", Role.caissier: "aucun", Role.gerant: "partiel", Role.responsable_achats: "partiel", Role.administrateur: "complet"}},
    {"module_action": "Initier un transfert de stock", "droits": {Role.vendeur: "aucun", Role.caissier: "aucun", Role.gerant: "partiel", Role.responsable_achats: "partiel", Role.administrateur: "complet"}},
    {"module_action": "Valider les dépenses au-delà d'un seuil", "droits": {Role.vendeur: "aucun", Role.caissier: "aucun", Role.gerant: "aucun", Role.responsable_achats: "complet", Role.administrateur: "complet"}},
    {"module_action": "Consulter le dashboard consolidé siège", "droits": {Role.vendeur: "aucun", Role.caissier: "aucun", Role.gerant: "aucun", Role.responsable_achats: "complet", Role.administrateur: "complet"}},
    {"module_action": "Gérer les droits utilisateurs", "droits": {Role.vendeur: "aucun", Role.caissier: "aucun", Role.gerant: "aucun", Role.responsable_achats: "aucun", Role.administrateur: "complet"}},
    {"module_action": "Créer / fermer une boutique", "droits": {Role.vendeur: "aucun", Role.caissier: "aucun", Role.gerant: "aucun", Role.responsable_achats: "aucun", Role.administrateur: "complet"}},
]

# --- Clients & paiements --------------------------------------------------------

CLIENTS: list[Client] = [
    Client(id="cli-kaba", nom="Ibrahima Kaba", contact="621 30 40 50", boutique_id="madina", segment="regulier", credit_autorise=True, solde_dette=210000),
    Client(id="cli-cisse", nom="Mariame Cissé", contact="628 90 11 22", boutique_id="lansanaya", segment="a_risque", credit_autorise=True, solde_dette=890000),
    Client(id="cli-barry", nom="Aissatou Barry", contact="622 15 60 70", boutique_id="lansanaya", segment="nouveau", credit_autorise=False, solde_dette=0),
    Client(id="cli-sylla", nom="Kadiatou Sylla", contact="655 44 33 22", boutique_id="matam", segment="fidele", credit_autorise=True, solde_dette=0),
    Client(id="cli-diallo-ao", nom="Alpha Oumar Diallo", contact="620 77 66 55", boutique_id="kankan", segment="regulier", credit_autorise=True, solde_dette=600000),
    Client(id="cli-toure", nom="Néné Touré", contact="626 12 34 56", boutique_id="matam", segment="fidele", credit_autorise=True, solde_dette=0),
    Client(id="cli-fofana", nom="Sory Fofana", contact="626 55 12 90", boutique_id="kaloum", segment="a_risque", credit_autorise=True, solde_dette=260000),
    Client(id="cli-barry-d", nom="Djénabou Barry", contact="621 90 40 10", boutique_id="madina", segment="regulier", credit_autorise=True, solde_dette=180000),
    Client(id="cli-conde", nom="Lansana Condé", contact="628 33 20 15", boutique_id="lansanaya", segment="a_risque", credit_autorise=True, solde_dette=710000),
]

PAIEMENTS_CLIENTS: list[PaiementClient] = [
    PaiementClient(id="pc-1", client_nom="Kadiatou Sylla", reference="#CMD-1040", boutique_id="matam", mode_paiement="mobile_money", date=date(2026, 8, 7), montant=890000, statut=StatutPaiement.encaisse),
    PaiementClient(id="pc-2", client_nom="Ibrahima Kaba", reference="Dette — remboursement", boutique_id="madina", mode_paiement="especes", date=date(2026, 8, 6), montant=240000, statut=StatutPaiement.encaisse),
    PaiementClient(id="pc-3", client_nom="Thierno Baldé", reference="#CMD-1037", boutique_id="lansanaya", mode_paiement="especes", date=date(2026, 8, 5), montant=48000, statut=StatutPaiement.encaisse),
    PaiementClient(id="pc-4", client_nom="Aissatou Barry", reference="#CMD-1042", boutique_id="lansanaya", mode_paiement="mobile_money", date=date(2026, 8, 8), montant=340000, statut=StatutPaiement.en_attente),
]

PAIEMENTS_FOURNISSEURS: list[PaiementFournisseur] = [
    PaiementFournisseur(id="pf-1", fournisseur_nom="Guinée Textiles", reference="#FR-317", boutique_id="lansanaya", mode_paiement="virement", date=date(2026, 8, 4), montant=6200000, statut=StatutPaiement.paye),
    PaiementFournisseur(id="pf-2", fournisseur_nom="Africa Electro", reference="#FR-313", boutique_id="lansanaya", mode_paiement="lettre_change", date=date(2026, 8, 1), montant=9300000, statut=StatutPaiement.partiel),
    PaiementFournisseur(id="pf-3", fournisseur_nom="Sotramag Import", reference="#FR-318", boutique_id="madina", mode_paiement="mobile_money", date=date(2026, 8, 10), montant=12400000, statut=StatutPaiement.en_attente),
]

# --- Produits & stock -----------------------------------------------------------

PRODUITS: list[Produit] = [
    Produit(id="robe-wax", nom="Robe wax femme (M)", secteur="habillement", categorie="Vêtements femme", prix=70000, unite="pièce", code_barres="6910000000011"),
    Produit(id="sandales-enfant", nom="Sandales enfant", secteur="habillement", categorie="Chaussures", prix=35000, unite="paire", code_barres="6910000000028"),
    Produit(id="chemise-homme", nom="Chemise homme (L)", secteur="habillement", categorie="Vêtements homme", prix=85000, unite="pièce", code_barres="6910000000035"),
    Produit(id="ensemble-wax-homme", nom="Ensemble wax homme", secteur="habillement", categorie="Vêtements homme", prix=120000, unite="pièce", code_barres="6910000000042"),
    Produit(id="riz-local", nom="Riz local 25kg", secteur="alimentation_generale", categorie="Céréales", prix=210000, unite="sac", code_barres="6910000000059", date_peremption=date(2027, 3, 1)),
    Produit(id="huile-vegetale", nom="Huile végétale 5L", secteur="alimentation_generale", categorie="Huiles", prix=68000, unite="bidon", code_barres="6910000000066", date_peremption=date(2026, 9, 30)),
    Produit(id="sucre-poudre", nom="Sucre en poudre 1kg", secteur="alimentation_generale", categorie="Épicerie", prix=9000, unite="paquet", code_barres="6910000000073"),
    Produit(id="ventilateur", nom="Ventilateur sur pied", secteur="electronique_electromenager", categorie="Électroménager", prix=380000, unite="pièce", code_barres="6910000000080"),
    Produit(id="refrigerateur", nom="Réfrigérateur 200L", secteur="electronique_electromenager", categorie="Électroménager", prix=2100000, unite="pièce", code_barres="6910000000097"),
    Produit(id="televiseur", nom="Téléviseur LED 43\"", secteur="electronique_electromenager", categorie="Électronique", prix=1450000, unite="pièce", code_barres="6910000000103"),
]

STOCKS: list[StockBoutique] = [
    StockBoutique(boutique_id="madina", produit_id="riz-local", quantite_disponible=5, quantite_reservee=3, seuil_alerte=15, derniere_mouvement=datetime(2026, 8, 8, 9, 14)),
    StockBoutique(boutique_id="lansanaya", produit_id="robe-wax", quantite_disponible=18, quantite_reservee=2, seuil_alerte=10, derniere_mouvement=datetime(2026, 8, 8, 8, 40)),
    StockBoutique(boutique_id="matam", produit_id="ventilateur", quantite_disponible=6, quantite_reservee=1, seuil_alerte=5, derniere_mouvement=datetime(2026, 8, 7, 17, 20)),
    StockBoutique(boutique_id="kankan", produit_id="huile-vegetale", quantite_disponible=4, quantite_reservee=0, seuil_alerte=12, derniere_mouvement=datetime(2026, 8, 5, 9, 0)),
    StockBoutique(boutique_id="kaloum", produit_id="chemise-homme", quantite_disponible=27, quantite_reservee=4, seuil_alerte=10, derniere_mouvement=datetime(2026, 8, 6, 10, 0)),
    StockBoutique(boutique_id="matam", produit_id="refrigerateur", quantite_disponible=3, quantite_reservee=1, seuil_alerte=4, derniere_mouvement=datetime(2026, 8, 4, 14, 0)),
    StockBoutique(boutique_id="madina", produit_id="sucre-poudre", quantite_disponible=62, quantite_reservee=8, seuil_alerte=20, derniere_mouvement=datetime(2026, 8, 3, 11, 0)),
    StockBoutique(boutique_id="lansanaya", produit_id="sandales-enfant", quantite_disponible=9, quantite_reservee=0, seuil_alerte=10, derniere_mouvement=datetime(2026, 8, 2, 15, 0)),
    StockBoutique(boutique_id="kaloum", produit_id="televiseur", quantite_disponible=2, quantite_reservee=1, seuil_alerte=3, derniere_mouvement=datetime(2026, 8, 6, 11, 30)),
    StockBoutique(boutique_id="kaloum", produit_id="ensemble-wax-homme", quantite_disponible=3, quantite_reservee=0, seuil_alerte=6, derniere_mouvement=datetime(2026, 8, 1, 9, 0)),
]

MOUVEMENTS_STOCK: list[MouvementStock] = [
    MouvementStock(id="mv-1", horodatage=datetime(2026, 8, 8, 9, 14), produit_id="riz-local", boutique_id="madina", motif=MotifMouvementStock.vente_caisse, operateur="I. Sow", quantite=-2),
    MouvementStock(id="mv-2", horodatage=datetime(2026, 8, 8, 8, 40), produit_id="robe-wax", boutique_id="lansanaya", motif=MotifMouvementStock.transfert_entrant, operateur="F. Bah", quantite=12),
    MouvementStock(id="mv-3", horodatage=datetime(2026, 8, 7, 17, 20), produit_id="ventilateur", boutique_id="matam", motif=MotifMouvementStock.achat_reception_fournisseur, operateur="A. Camara", quantite=10),
    MouvementStock(id="mv-4", horodatage=datetime(2026, 8, 7, 15, 5), produit_id="sucre-poudre", boutique_id="kankan", motif=MotifMouvementStock.casse_perte, operateur="M. Diallo", quantite=-3),
    MouvementStock(id="mv-5", horodatage=datetime(2026, 8, 6, 11, 30), produit_id="televiseur", boutique_id="kaloum", motif=MotifMouvementStock.correction_inventaire, operateur="A. Diané", quantite=-1),
    MouvementStock(id="mv-6", horodatage=datetime(2026, 8, 5, 9, 0), produit_id="huile-vegetale", boutique_id="kankan", motif=MotifMouvementStock.peremption, operateur="M. Diallo", quantite=-4),
]

ECARTS_INVENTAIRE: list[EcartInventaire] = [
    EcartInventaire(id="inv-1", produit_id="riz-local", boutique_id="madina", theorique=8, reel=5, statut="a_investiguer"),
    EcartInventaire(id="inv-2", produit_id="robe-wax", boutique_id="lansanaya", theorique=18, reel=18, statut="conforme"),
    EcartInventaire(id="inv-3", produit_id="televiseur", boutique_id="kaloum", theorique=3, reel=2, statut="corrige"),
]

# --- Caisse ---------------------------------------------------------------------

CAISSES: list[Caisse] = [
    Caisse(id="caisse-lansanaya-1", boutique_id="lansanaya", libelle="Principale", statut=StatutCaisse.ouverte, fond_initial=500000, solde_theorique=2140000, solde_reel=2140000, operateur="Fatoumata Bah"),
    Caisse(id="caisse-madina-1", boutique_id="madina", libelle="Principale", statut=StatutCaisse.ouverte, fond_initial=500000, solde_theorique=3620000, solde_reel=3575000, operateur="Ibrahima Sow"),
    Caisse(id="caisse-kankan-2", boutique_id="kankan", libelle="Secondaire", statut=StatutCaisse.ecart_signale, fond_initial=300000, solde_theorique=980000, solde_reel=935000, operateur="Mariama Diallo"),
    Caisse(id="caisse-matam-1", boutique_id="matam", libelle="Principale", statut=StatutCaisse.fermee, fond_initial=400000, solde_theorique=1410000, solde_reel=1410000, operateur="Alpha Camara"),
]

MOUVEMENTS_CAISSE: list[MouvementCaisse] = [
    MouvementCaisse(id="mc-1", horodatage=datetime(2026, 8, 8, 9, 14), boutique_id="lansanaya", caisse_libelle="Principale", type=TypeMouvementCaisse.encaissement, motif="Vente en caisse", operateur="F. Bah", montant=185000),
    MouvementCaisse(id="mc-2", horodatage=datetime(2026, 8, 8, 10, 2), boutique_id="madina", caisse_libelle="Principale", type=TypeMouvementCaisse.decaissement, motif="Dépense — transport", operateur="I. Sow", montant=-60000),
    MouvementCaisse(id="mc-3", horodatage=datetime(2026, 8, 8, 10, 45), boutique_id="kankan", caisse_libelle="Secondaire", type=TypeMouvementCaisse.encaissement, motif="Remboursement dette", operateur="M. Diallo", montant=120000),
    MouvementCaisse(id="mc-4", horodatage=datetime(2026, 8, 8, 11, 20), boutique_id="matam", caisse_libelle="Principale", type=TypeMouvementCaisse.encaissement, motif="Vente en caisse", operateur="A. Camara", montant=340000),
    MouvementCaisse(id="mc-5", horodatage=datetime(2026, 8, 8, 12, 5), boutique_id="lansanaya", caisse_libelle="Principale", type=TypeMouvementCaisse.decaissement, motif="Retrait fond de caisse", operateur="F. Bah", montant=-100000),
    MouvementCaisse(id="mc-6", horodatage=datetime(2026, 8, 8, 13, 30), boutique_id="madina", caisse_libelle="Principale", type=TypeMouvementCaisse.encaissement, motif="Vente en caisse", operateur="I. Sow", montant=275000),
]

# --- Commandes ----------------------------------------------------------------

COMMANDES_CLIENTS: list[CommandeClient] = [
    CommandeClient(id="CMD-1042", client_nom="Aissatou Barry", boutique_id="lansanaya", canal="mobile_client", mode_paiement="mobile_money", montant=340000, statut=StatutCommandeClient.en_preparation, date_creation=datetime(2026, 8, 10, 9, 20)),
    CommandeClient(id="CMD-1041", client_nom="Mamadou Diallo", boutique_id="madina", canal="boutique", mode_paiement="credit_client", montant=120000, statut=StatutCommandeClient.confirmee, date_creation=datetime(2026, 8, 9, 14, 10)),
    CommandeClient(id="CMD-1040", client_nom="Kadiatou Sylla", boutique_id="matam", canal="web", mode_paiement="mobile_money", montant=890000, statut=StatutCommandeClient.livree, date_creation=datetime(2026, 8, 7, 11, 5)),
    CommandeClient(id="CMD-1039", client_nom="Ousmane Bangoura", boutique_id="kaloum", canal="mobile_client", mode_paiement="a_la_livraison", montant=65000, statut=StatutCommandeClient.en_livraison, date_creation=datetime(2026, 8, 10, 8, 45)),
    CommandeClient(id="CMD-1038", client_nom="Fanta Camara", boutique_id="kankan", canal="mobile_client", mode_paiement="mobile_money", montant=210000, statut=StatutCommandeClient.annulee, date_creation=datetime(2026, 8, 6, 16, 30)),
    CommandeClient(id="CMD-1037", client_nom="Thierno Baldé", boutique_id="lansanaya", canal="boutique", mode_paiement="especes", montant=48000, statut=StatutCommandeClient.livree, date_creation=datetime(2026, 8, 5, 10, 0)),
    CommandeClient(id="CMD-1036", client_nom="Hawa Keita", boutique_id="madina", canal="web", mode_paiement="mobile_money", montant=155000, statut=StatutCommandeClient.en_attente, date_creation=datetime(2026, 8, 10, 7, 55)),
    CommandeClient(id="CMD-1035", client_nom="Sékou Touré", boutique_id="matam", canal="mobile_client", mode_paiement="credit_client", montant=1240000, statut=StatutCommandeClient.confirmee, date_creation=datetime(2026, 8, 4, 13, 15)),
]

COMMANDES_FOURNISSEURS: list[LigneCommandeFournisseur] = [
    LigneCommandeFournisseur(id="FR-318", fournisseur_id="sotramag", boutique_id="madina", date_attendue=date(2026, 8, 5), montant=12400000, statut=StatutCommandeFournisseur.envoyee),
    LigneCommandeFournisseur(id="FR-317", fournisseur_id="guinee-textiles", boutique_id="lansanaya", date_attendue=date(2026, 8, 4), montant=6200000, statut=StatutCommandeFournisseur.receptionnee),
    LigneCommandeFournisseur(id="FR-316", fournisseur_id="africa-electro", boutique_id="matam", date_attendue=date(2026, 8, 8), montant=18900000, statut=StatutCommandeFournisseur.validee),
    LigneCommandeFournisseur(id="FR-315", fournisseur_id="grossiste-kaloum", boutique_id="kaloum", date_attendue=date(2026, 8, 2), montant=3100000, statut=StatutCommandeFournisseur.cloturee),
    LigneCommandeFournisseur(id="FR-314", fournisseur_id="sotramag", boutique_id="kankan", date_attendue=date(2026, 8, 10), montant=7850000, statut=StatutCommandeFournisseur.brouillon),
    LigneCommandeFournisseur(id="FR-313", fournisseur_id="africa-electro", boutique_id="lansanaya", date_attendue=date(2026, 8, 1), montant=9300000, statut=StatutCommandeFournisseur.receptionnee_partielle),
]

# --- Livraisons -----------------------------------------------------------------

LIVRAISONS: list[Livraison] = [
    Livraison(id="liv-1042", commande_id="CMD-1042", livreur="Ousmane Barry", boutique_id="lansanaya", adresse="Lansanaya, Ratoma", creneau="Aujourd'hui, 14h-18h", statut=StatutLivraison.en_cours, preuve_url=None),
    Livraison(id="liv-1040", commande_id="CMD-1040", livreur="Sécurité Express", boutique_id="matam", adresse="Matam centre", creneau="Livrée hier", statut=StatutLivraison.livree, preuve_url=None),
    Livraison(id="liv-1039", commande_id="CMD-1039", livreur="Mamadi Touré", boutique_id="kaloum", adresse="Kaloum, rue KA-025", creneau="Aujourd'hui, 10h-13h", statut=StatutLivraison.preparee, preuve_url=None),
    Livraison(id="liv-1035", commande_id="CMD-1035", livreur="Sécurité Express", boutique_id="matam", adresse="Matoto, Conakry", creneau="Hier, 16h-18h", statut=StatutLivraison.echec, preuve_url=None),
]

# --- Dépenses -------------------------------------------------------------------

DEPENSES: list[Depense] = [
    Depense(id="dep-1", boutique_id="madina", categorie="Transport", auteur="Ibrahima Sow", date=date(2026, 8, 7), montant=60000, statut_validation=StatutValidationDepense.auto_validee, justificatif_disponible=True),
    Depense(id="dep-2", boutique_id="lansanaya", categorie="Électricité", auteur="Fatoumata Bah", date=date(2026, 8, 6), montant=450000, statut_validation=StatutValidationDepense.en_attente, justificatif_disponible=True),
    Depense(id="dep-3", boutique_id="matam", categorie="Fournitures", auteur="Alpha Camara", date=date(2026, 8, 5), montant=38000, statut_validation=StatutValidationDepense.auto_validee, justificatif_disponible=False),
    Depense(id="dep-4", boutique_id="kankan", categorie="Loyer", auteur="Mariama Diallo", date=date(2026, 8, 1), montant=1200000, statut_validation=StatutValidationDepense.validee_siege, justificatif_disponible=True),
]

# --- Dettes / créances -----------------------------------------------------------

DETTES: list[Dette] = [
    Dette(id="cre-1", tiers_type=TiersType.client, tiers_nom="Ibrahima Kaba", boutique_id="madina", montant_initial=450000, solde_restant=210000, echeance=date(2026, 8, 10), statut=StatutDette.en_cours),
    Dette(id="cre-2", tiers_type=TiersType.client, tiers_nom="Mariame Cissé", boutique_id="lansanaya", montant_initial=890000, solde_restant=890000, echeance=date(2026, 8, 6), statut=StatutDette.en_retard),
    Dette(id="cre-3", tiers_type=TiersType.client, tiers_nom="Alpha Oumar Diallo", boutique_id="kankan", montant_initial=1200000, solde_restant=600000, echeance=date(2026, 8, 15), statut=StatutDette.en_cours),
    Dette(id="cre-4", tiers_type=TiersType.client, tiers_nom="Néné Touré", boutique_id="matam", montant_initial=320000, solde_restant=0, echeance=date(2026, 8, 1), statut=StatutDette.soldee),
    Dette(id="cre-5", tiers_type=TiersType.client, tiers_nom="Sory Fofana", boutique_id="kaloum", montant_initial=260000, solde_restant=260000, echeance=date(2026, 8, 5), statut=StatutDette.en_retard),
    Dette(id="cre-6", tiers_type=TiersType.client, tiers_nom="Djénabou Barry", boutique_id="madina", montant_initial=540000, solde_restant=180000, echeance=date(2026, 8, 20), statut=StatutDette.en_cours),
    Dette(id="cre-7", tiers_type=TiersType.client, tiers_nom="Lansana Condé", boutique_id="lansanaya", montant_initial=710000, solde_restant=710000, echeance=date(2026, 8, 7), statut=StatutDette.en_retard),
    Dette(id="det-1", tiers_type=TiersType.fournisseur, tiers_nom="Sotramag Import", boutique_id="madina", montant_initial=12400000, solde_restant=12400000, echeance=date(2026, 9, 15), statut=StatutDette.en_cours),
    Dette(id="det-2", tiers_type=TiersType.fournisseur, tiers_nom="Africa Electro", boutique_id="lansanaya", montant_initial=9300000, solde_restant=3100000, echeance=date(2026, 9, 1), statut=StatutDette.en_cours),
    Dette(id="det-3", tiers_type=TiersType.fournisseur, tiers_nom="Guinée Textiles", boutique_id="lansanaya", montant_initial=6200000, solde_restant=0, echeance=date(2026, 8, 4), statut=StatutDette.soldee),
]

REMBOURSEMENTS: list[Remboursement] = [
    Remboursement(id="rb-1", dette_id="cre-1", montant=240000, mode_paiement="especes", date=date(2026, 8, 6), operateur="I. Sow"),
]

# --- Transferts de stock -----------------------------------------------------------

TRANSFERTS: list[TransfertStock] = [
    TransfertStock(id="TR-201", produit_id="riz-local", boutique_source_id="lansanaya", boutique_destination_id="madina", quantite=40, demandeur="I. Sow (gérant)", statut=StatutTransfert.en_transit),
    TransfertStock(id="TR-202", produit_id="ventilateur", boutique_source_id="matam", boutique_destination_id="kaloum", quantite=5, demandeur="Siège", statut=StatutTransfert.valide),
    TransfertStock(id="TR-203", produit_id="robe-wax", boutique_source_id="kaloum", boutique_destination_id="lansanaya", quantite=12, demandeur="F. Bah (gérante)", statut=StatutTransfert.recu),
    TransfertStock(id="TR-204", produit_id="huile-vegetale", boutique_source_id="madina", boutique_destination_id="kankan", quantite=30, demandeur="M. Diallo (gérante)", statut=StatutTransfert.demande),
    TransfertStock(id="TR-205", produit_id="televiseur", boutique_source_id="matam", boutique_destination_id="lansanaya", quantite=2, demandeur="Siège", statut=StatutTransfert.en_transit),
    TransfertStock(id="TR-206", produit_id="sucre-poudre", boutique_source_id="lansanaya", boutique_destination_id="kaloum", quantite=50, demandeur="A. Camara (gérant)", statut=StatutTransfert.recu),
]

# --- Promotions & tarifs ------------------------------------------------------------

PROMOTIONS: list[Promotion] = [
    Promotion(id="promo-1", nom="-15 % sur les robes wax", boutique_id="lansanaya", secteur="habillement", origine="ia", impact_estime="+18 % de ventes estimées", statut=StatutPromotion.en_attente_validation),
    Promotion(id="promo-2", nom="Déstockage huile 5L", boutique_id="madina", secteur="alimentation_generale", origine="gerant", impact_estime="Écoulement stock à rotation lente", statut=StatutPromotion.active),
    Promotion(id="promo-3", nom="Fin de saison ventilateurs", boutique_id="matam", secteur="electronique_electromenager", origine="ia", impact_estime="Marge réduite, rotation accélérée", statut=StatutPromotion.validee),
    Promotion(id="promo-4", nom="Programme fidélité — points doublés", boutique_id=None, secteur=None, origine="direction", impact_estime="Fidélisation clients récurrents", statut=StatutPromotion.active),
]

# --- Intelligence artificielle -------------------------------------------------------

SUGGESTIONS_REAPPRO: list[SuggestionReapprovisionnement] = [
    SuggestionReapprovisionnement(produit_id="riz-local", boutique_id="madina", stock_actuel=5, ventes_prevues_14j=42, quantite_suggeree=45),
    SuggestionReapprovisionnement(produit_id="huile-vegetale", boutique_id="kankan", stock_actuel=4, ventes_prevues_14j=26, quantite_suggeree=28),
    SuggestionReapprovisionnement(produit_id="robe-wax", boutique_id="lansanaya", stock_actuel=18, ventes_prevues_14j=30, quantite_suggeree=15),
    SuggestionReapprovisionnement(produit_id="ventilateur", boutique_id="matam", stock_actuel=6, ventes_prevues_14j=9, quantite_suggeree=6),
    SuggestionReapprovisionnement(produit_id="televiseur", boutique_id="kaloum", stock_actuel=2, ventes_prevues_14j=5, quantite_suggeree=4),
]

SYNTHESE_REPORTING = (
    "Le réseau a réalisé 412,6 M GNF de chiffre d'affaires cette semaine, en hausse de 6 % par rapport "
    "à la semaine précédente, portée par Madina et Lansanaya. La boutique Kankan reste en marge négative "
    "pour le second mois consécutif, principalement du fait de charges de loyer élevées rapportées à son "
    "volume de ventes. Le taux de recouvrement des créances clients s'établit à 78 %, stable. Le secteur "
    "habillement enregistre la meilleure progression (+12 %), tiré par les robes wax à Lansanaya."
)

ANOMALIES_REPORTING: list[AnomalieReporting] = [
    AnomalieReporting(id="an-1", titre="Marge négative persistante — Kankan", description="Deuxième mois consécutif sous le seuil de rentabilité, à surveiller par le siège."),
    AnomalieReporting(id="an-2", titre="Pic d'écarts de caisse — réseau", description="3 écarts de caisse signalés cette semaine contre une moyenne de 0,5."),
    AnomalieReporting(id="an-3", titre="Rupture récurrente — Riz local 25kg", description="Troisième semaine consécutive sous le seuil d'alerte à Madina."),
    AnomalieReporting(id="an-4", titre="Hausse inhabituelle des retours", description="Habillement, boutique Kaloum : retours en hausse de 40 % vs moyenne."),
]

CHATBOT_CONFIG = {
    "chatbot_actif": True,
    "suivi_commande_automatique": True,
    "relance_echeances_dette": True,
    "escalade_operateur_humain": True,
    "reponses_langue_locale_test": False,
}

CHATBOT_CONVERSATION_DEMO: list[dict] = [
    {"auteur": "client", "texte": "Bonjour, où en est ma commande #CMD-1042 ?"},
    {"auteur": "bot", "texte": "Votre commande est en préparation à la boutique Lansanaya. Livraison estimée aujourd'hui avant 18h."},
    {"auteur": "client", "texte": "Merci. Je peux aussi rembourser ma dette depuis ici ?"},
    {"auteur": "bot", "texte": "Oui, votre solde est de 210 000 GNF. Voulez-vous initier un remboursement ? Il sera validé par votre boutique."},
    {"auteur": "client", "texte": "Oui, 100 000 GNF pour commencer."},
    {"auteur": "bot", "texte": "Demande transmise à la boutique Madina pour validation. Vous recevrez une confirmation."},
]

# --- Sécurité & audit ---------------------------------------------------------------

JOURNAL_AUDIT: list[JournalAuditEntry] = [
    JournalAuditEntry(id="aud-1", horodatage=datetime(2026, 8, 8, 11, 2), action="Modification des droits — S. Bah passé en lecture seule", auteur="Sékou Condé", boutique_id=None),
    JournalAuditEntry(id="aud-2", horodatage=datetime(2026, 8, 8, 10, 40), action="Validation transfert de stock #TR-208", auteur="Mamadouba Keita", boutique_id=None),
    JournalAuditEntry(id="aud-3", horodatage=datetime(2026, 8, 8, 9, 15), action="Écart de caisse signalé (45 000 GNF)", auteur="Mariama Diallo", boutique_id="kankan"),
    JournalAuditEntry(id="aud-4", horodatage=datetime(2026, 8, 7, 18, 22), action="Dépense validée — loyer 1 200 000 GNF", auteur="Sékou Condé", boutique_id="kankan"),
    JournalAuditEntry(id="aud-5", horodatage=datetime(2026, 8, 7, 15, 3), action="Nouvelle commande fournisseur #FR-318", auteur="Ibrahima Sow", boutique_id="madina"),
    JournalAuditEntry(id="aud-6", horodatage=datetime(2026, 8, 7, 9, 47), action="Connexion échouée x3 — compte verrouillé", auteur="Souleymane Bah", boutique_id="kaloum"),
    JournalAuditEntry(id="aud-7", horodatage=datetime(2026, 8, 5, 16, 10), action="Correction d'inventaire — écart +4 unités", auteur="Alpha Camara", boutique_id="matam"),
]

PARAMETRES_SECURITE: list[ParametreSecurite] = [
    ParametreSecurite(label="Authentification à deux facteurs — comptes sensibles", actif=True),
    ParametreSecurite(label="Verrouillage après 5 tentatives échouées", actif=True),
    ParametreSecurite(label="Expiration de session après inactivité", actif=True),
    ParametreSecurite(label="Double validation — dépenses & transferts significatifs", actif=True),
    ParametreSecurite(label="Restriction par terminal — comptes siège", actif=False),
]

# --- Paramètres / référentiels -------------------------------------------------------

REFERENTIELS: dict[str, list[ReferentielItem]] = {
    "secteurs": [
        ReferentielItem(id="habillement", nom="Habillement"),
        ReferentielItem(id="alimentation_generale", nom="Alimentation générale"),
        ReferentielItem(id="electronique_electromenager", nom="Électronique/Électroménager"),
    ],
    "villes": [
        ReferentielItem(id="conakry", nom="Conakry"),
        ReferentielItem(id="kankan", nom="Kankan"),
    ],
    "communes": [
        ReferentielItem(id="ratoma", nom="Ratoma"),
        ReferentielItem(id="kaloum", nom="Kaloum"),
        ReferentielItem(id="matoto", nom="Matoto"),
        ReferentielItem(id="kankan-centre", nom="Kankan Centre"),
    ],
    "quartiers": [
        ReferentielItem(id="lansanaya", nom="Lansanaya"),
        ReferentielItem(id="madina", nom="Madina"),
        ReferentielItem(id="matam", nom="Matam"),
        ReferentielItem(id="kaloum-centre", nom="Kaloum centre"),
        ReferentielItem(id="centre-ville", nom="Centre-ville"),
    ],
    "canaux_vente": [
        ReferentielItem(id="web", nom="Web"),
        ReferentielItem(id="mobile_client", nom="Mobile client"),
        ReferentielItem(id="boutique", nom="Boutique"),
    ],
    "modes_paiement": [
        ReferentielItem(id="especes", nom="Espèces"),
        ReferentielItem(id="mobile_money", nom="Mobile Money"),
        ReferentielItem(id="virement", nom="Virement"),
        ReferentielItem(id="lettre_change", nom="Lettre de change"),
        ReferentielItem(id="credit_client", nom="Crédit client"),
        ReferentielItem(id="a_la_livraison", nom="À la livraison"),
    ],
    "categories_depenses": [
        ReferentielItem(id="loyer", nom="Loyer"),
        ReferentielItem(id="electricite", nom="Électricité"),
        ReferentielItem(id="transport", nom="Transport"),
        ReferentielItem(id="fournitures", nom="Fournitures"),
        ReferentielItem(id="salaires_ponctuels", nom="Salaires ponctuels"),
    ],
    "categories_produits": [
        ReferentielItem(id="vetements-homme", nom="Vêtements homme"),
        ReferentielItem(id="vetements-femme", nom="Vêtements femme"),
        ReferentielItem(id="chaussures", nom="Chaussures"),
        ReferentielItem(id="cereales", nom="Céréales"),
        ReferentielItem(id="huiles", nom="Huiles"),
        ReferentielItem(id="epicerie", nom="Épicerie"),
        ReferentielItem(id="electromenager", nom="Électroménager"),
        ReferentielItem(id="electronique", nom="Électronique"),
    ],
    "caisses_comptes": [
        ReferentielItem(id="caisse-principale", nom="Caisse principale"),
        ReferentielItem(id="caisse-secondaire", nom="Caisse secondaire"),
    ],
    "livreurs": [
        ReferentielItem(id="ousmane-barry", nom="Ousmane Barry"),
        ReferentielItem(id="mamadi-toure", nom="Mamadi Touré"),
        ReferentielItem(id="securite-express", nom="Sécurité Express"),
    ],
}

