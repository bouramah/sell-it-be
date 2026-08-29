from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


# --- Enums ---------------------------------------------------------------
#
# Secteur n'est plus un enum fixe : c'est un référentiel géré (catégorie
# "secteurs" dans la table referentiels), au même titre que quartiers/villes.
# Les champs "secteur"/"secteurs" ci-dessous sont donc de simples str.
#
# Role n'est plus non plus un enum fixe : c'est une entité en base (table
# `roles` — id, libellé, portée), créable/modifiable depuis Utilisateurs &
# droits sans développement, cf. CDC §3.3. Les champs "role" ci-dessous sont
# donc de simples str (l'id du rôle) ; voir RoleInfo pour le schéma complet.


class StatutBoutique(str, Enum):
    active = "active"
    fermee = "fermee"
    en_creation = "en_creation"


class DroitAcces(str, Enum):
    complet = "complet"
    lecture_seule = "lecture_seule"
    partiel = "partiel"
    aucun = "aucun"


class SegmentClient(str, Enum):
    nouveau = "nouveau"
    regulier = "regulier"
    fidele = "fidele"
    a_risque = "a_risque"


class StatutDette(str, Enum):
    en_cours = "en_cours"
    en_retard = "en_retard"
    soldee = "soldee"


class TiersType(str, Enum):
    client = "client"
    fournisseur = "fournisseur"


class StatutDemandeCredit(str, Enum):
    en_attente = "en_attente"
    validee = "validee"
    refusee = "refusee"


class StatutEtablissement(str, Enum):
    active = "active"
    inactive = "inactive"


class TypeGarant(str, Enum):
    referent = "referent"
    comptabilite = "comptabilite"


class StatutValidationGarant(str, Enum):
    en_attente = "en_attente"
    validee = "validee"
    refusee = "refusee"


class StatutPaiement(str, Enum):
    encaisse = "encaisse"
    en_attente = "en_attente"
    paye = "paye"
    partiel = "partiel"


class ModePaiement(str, Enum):
    especes = "especes"
    mobile_money = "mobile_money"
    a_la_livraison = "a_la_livraison"
    credit_client = "credit_client"
    virement = "virement"
    lettre_change = "lettre_change"


class StatutCaisse(str, Enum):
    ouverte = "ouverte"
    fermee = "fermee"
    ecart_signale = "ecart_signale"


class TypeMouvementCaisse(str, Enum):
    encaissement = "encaissement"
    decaissement = "decaissement"


class CanalCommande(str, Enum):
    web = "web"
    mobile_client = "mobile_client"
    boutique = "boutique"


class StatutCommandeClient(str, Enum):
    en_attente = "en_attente"
    confirmee = "confirmee"
    en_preparation = "en_preparation"
    en_livraison = "en_livraison"
    livree = "livree"
    annulee = "annulee"


class StatutCommandeFournisseur(str, Enum):
    brouillon = "brouillon"
    validee = "validee"
    envoyee = "envoyee"
    receptionnee_partielle = "receptionnee_partielle"
    receptionnee = "receptionnee"
    cloturee = "cloturee"


class StatutLivraison(str, Enum):
    preparee = "preparee"
    en_cours = "en_cours"
    livree = "livree"
    echec = "echec"


class StatutValidationDepense(str, Enum):
    auto_validee = "auto_validee"
    en_attente = "en_attente"
    validee_siege = "validee_siege"


class StatutValidationRemise(str, Enum):
    aucune = "aucune"
    en_attente = "en_attente"
    validee = "validee"


class StatutTransfert(str, Enum):
    demande = "demande"
    valide = "valide"
    en_transit = "en_transit"
    recu = "recu"


class MotifMouvementStock(str, Enum):
    vente_caisse = "vente_caisse"
    commande_client = "commande_client"
    achat_reception_fournisseur = "achat_reception_fournisseur"
    transfert_entrant = "transfert_entrant"
    transfert_sortant = "transfert_sortant"
    retour_client = "retour_client"
    casse_perte = "casse_perte"
    peremption = "peremption"
    correction_inventaire = "correction_inventaire"
    don_echantillon = "don_echantillon"
    autre = "autre"


class OriginePromotion(str, Enum):
    ia = "ia"
    gerant = "gerant"
    direction = "direction"


class StatutPromotion(str, Enum):
    en_attente_validation = "en_attente_validation"
    validee = "validee"
    active = "active"
    terminee = "terminee"


# --- Réseau ----------------------------------------------------------------

class Boutique(BaseModel):
    id: str
    nom: str
    secteurs: list[str]
    quartier: str
    commune: str
    ville: str
    horaires: str
    responsable: str
    statut: StatutBoutique
    telephone: str
    latitude: float | None = None
    longitude: float | None = None
    secteur_geo_id: str | None = None


class Fournisseur(BaseModel):
    id: str
    nom: str
    secteur: str
    conditions_paiement: str
    contact: str
    secteur_geo_id: str | None = None


class TopFournisseur(BaseModel):
    fournisseur_id: str
    fournisseur_nom: str
    montant_achats: float
    nombre_commandes: int


class Utilisateur(BaseModel):
    id: str
    nom: str
    prenom: str
    contact: str
    role: str
    boutique_ids: list[str]
    statut: str
    derniere_connexion: datetime | None = None
    secteur_geo_id: str | None = None


class PermissionLigne(BaseModel):
    module_action: str
    droits: dict[str, DroitAcces]


class RoleInfo(BaseModel):
    id: str
    libelle: str
    portee: str
    systeme: bool


# --- Découpage administratif (Région > Ville > Commune > Quartier > Secteur) ------------------

class Region(BaseModel):
    id: str
    nom: str


class Ville(BaseModel):
    id: str
    nom: str
    region_id: str


class Commune(BaseModel):
    id: str
    nom: str
    ville_id: str


class QuartierGeo(BaseModel):
    id: str
    nom: str
    commune_id: str


class SecteurGeo(BaseModel):
    id: str
    nom: str
    quartier_id: str


# --- Clients & paiements ----------------------------------------------------

class Client(BaseModel):
    id: str
    nom: str
    contact: str
    boutique_ids: list[str]
    segment: SegmentClient
    credit_autorise: bool
    solde_dette: float
    quartier: str | None = None
    commune: str | None = None
    ville: str | None = None
    secteur_geo_id: str | None = None


class TopClient(BaseModel):
    client_id: str
    client_nom: str
    chiffre_affaires: float
    nombre_commandes: int


class PaiementClient(BaseModel):
    id: str
    client_nom: str
    reference: str  # commande liée ou "Dette — remboursement"
    boutique_id: str
    caisse_id: str | None = None
    mode_paiement: ModePaiement
    date: date
    montant: float
    statut: StatutPaiement


class PaiementFournisseur(BaseModel):
    id: str
    fournisseur_nom: str
    reference: str
    boutique_id: str
    caisse_id: str | None = None
    mode_paiement: ModePaiement
    date: date
    montant: float
    statut: StatutPaiement
    document_url: str | None = None


# --- Produits & stock --------------------------------------------------------

class ProduitImage(BaseModel):
    id: str
    url: str
    position: int


class PalierPrix(str, Enum):
    detail = "detail"
    semi_gros = "semi_gros"
    gros = "gros"


class Produit(BaseModel):
    id: str
    nom: str
    secteur: str
    categorie: str
    prix_detail: float
    prix_semi_gros: float
    prix_gros: float
    seuil_semi_gros: int = 10
    seuil_gros: int = 50
    unite: str
    code_barres: str
    date_peremption: date | None = None
    images: list[ProduitImage] = []


class PrixPeriode(BaseModel):
    id: str
    produit_id: str
    boutique_id: str | None = None
    palier: PalierPrix
    prix: float
    date_debut: date
    date_fin: date | None = None
    modifie_par: str
    cree_le: datetime


class PrixAchat(BaseModel):
    id: str
    produit_id: str
    fournisseur_id: str
    palier: PalierPrix
    prix: float
    date_debut: date
    date_fin: date | None = None
    modifie_par: str
    cree_le: datetime


class StockBoutique(BaseModel):
    boutique_id: str
    produit_id: str
    quantite_disponible: int
    quantite_reservee: int
    seuil_alerte: int
    derniere_mouvement: datetime


class MouvementStock(BaseModel):
    id: str
    horodatage: datetime
    produit_id: str
    boutique_id: str
    motif: MotifMouvementStock
    operateur: str
    quantite: int  # signé
    stock_avant: int
    stock_apres: int


class StatutEcartInventaire(str, Enum):
    conforme = "conforme"
    a_investiguer = "a_investiguer"
    corrige = "corrige"


class EcartInventaire(BaseModel):
    id: str
    produit_id: str
    boutique_id: str
    theorique: int
    reel: int
    statut: StatutEcartInventaire


# --- Caisse -----------------------------------------------------------------

class Caisse(BaseModel):
    id: str
    boutique_id: str
    libelle: str
    statut: StatutCaisse
    fond_initial: float
    solde_theorique: float
    solde_reel: float
    operateur: str


class MouvementCaisse(BaseModel):
    id: str
    horodatage: datetime
    boutique_id: str
    caisse_libelle: str
    type: TypeMouvementCaisse
    motif: str
    operateur: str
    montant: float  # signé
    solde_avant: float
    solde_apres: float


# --- Commandes ----------------------------------------------------------------

class CommandeClient(BaseModel):
    id: str
    client_nom: str
    client_id: str | None = None
    boutique_id: str
    canal: CanalCommande
    mode_paiement: ModePaiement
    montant: float
    statut: StatutCommandeClient
    date_creation: datetime
    remise_statut: StatutValidationRemise = StatutValidationRemise.aucune
    remise_motif: str | None = None
    remise_validee_par: str | None = None
    remise_validee_le: datetime | None = None


class ArticleCommande(BaseModel):
    id: str
    produit_id: str
    produit_nom: str
    quantite: int
    palier: PalierPrix
    prix_unitaire: float
    prix_catalogue_a_la_vente: float | None = None


class CommandeClientDetail(CommandeClient):
    articles: list[ArticleCommande]


class LigneCommandeFournisseur(BaseModel):
    id: str
    fournisseur_id: str
    boutique_id: str
    date_attendue: date
    montant: float
    statut: StatutCommandeFournisseur
    date_reception: date | None = None


class ArticleCommandeFournisseur(BaseModel):
    # Pas de palier détail/semi-gros/gros ici : ce ne sont pas des prix de vente client,
    # cf. commandes.py — un achat fournisseur n'est pas rattaché à ArticleCommande.
    id: str
    produit_id: str
    produit_nom: str
    quantite: int
    prix_unitaire: float
    quantite_recue: int


class CommandeFournisseurDetail(LigneCommandeFournisseur):
    articles: list[ArticleCommandeFournisseur]


# --- Livraisons ---------------------------------------------------------------

class Livraison(BaseModel):
    id: str
    commande_id: str
    livreur: str
    livreur_user_id: str | None = None
    boutique_id: str
    adresse: str
    creneau: str
    statut: StatutLivraison
    preuve_url: str | None = None


# --- Dépenses -------------------------------------------------------------------

class Depense(BaseModel):
    id: str
    boutique_id: str
    caisse_id: str | None = None
    categorie: str
    auteur: str
    date: date
    montant: float
    statut_validation: StatutValidationDepense
    justificatif_url: str | None = None


# --- Dettes / créances -----------------------------------------------------------

class Dette(BaseModel):
    id: str
    tiers_type: TiersType
    tiers_nom: str
    boutique_id: str
    montant_initial: float
    solde_restant: float
    echeance: date
    statut: StatutDette


class Remboursement(BaseModel):
    id: str
    dette_id: str
    caisse_id: str | None = None
    montant: float
    mode_paiement: ModePaiement
    date: date
    operateur: str


class DemandeCredit(BaseModel):
    """Demande de crédit initiée par un client depuis l'appli mobile (CDC §3.1/§3.8) —
    reçue et validée par la boutique avant toute prise en compte effective (jamais de
    dette créée automatiquement à la demande)."""
    id: str
    client_id: str
    client_nom: str
    boutique_id: str
    montant_souhaite: float
    motif: str
    statut: StatutDemandeCredit
    date_creation: datetime


# --- Aide Humanitaire -----------------------------------------------------------

class Etablissement(BaseModel):
    id: str
    nom: str
    type_etablissement: str
    adresse: str | None = None
    referent_nom: str
    referent_contact: str
    comptabilite_nom: str
    comptabilite_contact: str
    statut: StatutEtablissement


class Beneficiaire(BaseModel):
    id: str
    client_id: str
    client_nom: str
    client_contact: str
    etablissement_id: str
    etablissement_nom: str
    numero_membre: str
    poste: str
    # None si l'appelant n'a pas le droit de voir cette donnée (réservé à l'administrateur) —
    # jamais un chiffre inventé ou masqué autrement qu'en l'omettant explicitement.
    salaire_reference: float | None = None
    engagement_signe_url: str | None = None
    engagement_signe_date: date | None = None
    plafond_suspendu: bool
    plafond_disponible: float
    credit_autorise: bool


class BaremeCreditBeneficiaire(BaseModel):
    id: str
    etablissement_id: str | None = None
    etablissement_nom: str | None = None
    poste: str
    plafond: float
    date_debut: date
    date_fin: date | None = None


class ValidationGarantCredit(BaseModel):
    id: str
    type_garant: TypeGarant
    nom_garant: str
    statut: StatutValidationGarant
    date_reponse: datetime | None = None
    motif_refus: str | None = None


class ValidationGarantDetail(BaseModel):
    """Vue publique (jeton) d'une demande de crédit Aide Humanitaire à valider — jamais de donnée
    non nécessaire à la décision du garant (le salaire n'apparaît que sur le jeton comptabilité)."""
    beneficiaire_nom: str
    etablissement_nom: str
    poste: str
    montant_souhaite: float
    motif: str
    salaire_reference: float | None = None
    type_garant: TypeGarant
    statut: StatutValidationGarant
    autre_garant_statut: StatutValidationGarant
    expire_le: datetime


class ValidationGarantDecision(BaseModel):
    approuve: bool
    motif_refus: str | None = None


class VersementEtablissement(BaseModel):
    id: str
    etablissement_id: str
    etablissement_nom: str
    montant: float
    date: date
    reference: str | None = None
    justificatif_url: str | None = None
    note: str | None = None


class SuiviEtablissement(BaseModel):
    etablissement_id: str
    etablissement_nom: str
    nombre_beneficiaires: int
    credits_en_cours: float
    credits_en_retard: float
    montant_verse: float
    ecart: float


# --- Transferts de stock -----------------------------------------------------------

class LigneTransfertStock(BaseModel):
    id: str
    produit_id: str
    produit_nom: str
    quantite: int
    quantite_recue: int | None = None
    motif_ecart: str | None = None


class TransfertStock(BaseModel):
    id: str
    boutique_source_id: str
    boutique_destination_id: str
    demandeur: str
    statut: StatutTransfert
    lignes: list[LigneTransfertStock]


# --- Comptabilité ------------------------------------------------------------------

class CompteResultatBoutique(BaseModel):
    boutique_id: str
    chiffre_affaires: float
    achats: float
    depenses: float
    marge_nette: float


class EcritureComptable(BaseModel):
    """Ligne du journal des opérations (CDC §3.14/§7.3) : chaque écriture est reliée à son
    opération source (vente, achat, dépense, remboursement) et à l'utilisateur qui l'a
    enregistrée — jamais saisie manuellement, toujours dérivée d'une opération déjà
    enregistrée dans un autre module (pas de double saisie)."""
    id: str
    date: str
    boutique_id: str
    nature: str
    sens: str
    montant: float
    libelle: str
    auteur: str | None
    operation_source_type: str
    operation_source_id: str


class LigneStockValorise(BaseModel):
    boutique_id: str
    produit_id: str
    produit_nom: str
    quantite: int
    cout_unitaire_moyen: float | None
    valeur: float


class EtatStockValorise(BaseModel):
    lignes: list[LigneStockValorise]
    valeur_totale: float


class LigneMargeProduit(BaseModel):
    produit_id: str
    produit_nom: str
    quantite_vendue: int
    chiffre_affaires: float
    cout_total: float | None  # None si aucun prix d'achat renseigné pour ce produit sur la période
    marge: float | None
    marge_pct: float | None


class MargeProduits(BaseModel):
    date_debut: datetime
    date_fin: datetime
    boutique_id: str | None
    chiffre_affaires_total: float
    marge_totale: float | None
    lignes: list[LigneMargeProduit]


# --- Promotions & tarifs ------------------------------------------------------------

class Promotion(BaseModel):
    id: str
    nom: str
    boutique_id: str | None
    secteur: str | None
    origine: OriginePromotion
    impact_estime: str
    statut: StatutPromotion


# --- Intelligence artificielle -------------------------------------------------------

class SuggestionReapprovisionnement(BaseModel):
    produit_id: str
    boutique_id: str
    stock_actuel: int
    ventes_prevues_14j: int
    quantite_suggeree: int


class AnomalieReporting(BaseModel):
    id: str
    titre: str
    description: str


class ConversationMessage(BaseModel):
    auteur: str  # "client" | "bot"
    texte: str


# --- Sécurité & audit ---------------------------------------------------------------

class JournalAuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    horodatage: datetime
    action: str
    auteur: str
    boutique_id: str | None
    utilisateur_id: str | None = None
    client_id: str | None = None
    canal: str | None = None
    methode: str | None = None
    chemin: str | None = None
    statut_code: int | None = None


class JournalAuditPage(BaseModel):
    items: list[JournalAuditEntry]
    total: int


class ParametreSecurite(BaseModel):
    id: str
    label: str
    actif: bool


class ParametreApplication(BaseModel):
    id: str
    label: str
    actif: bool


class ParametreFiscal(BaseModel):
    taux: float
    actif: bool


# --- Paramètres / référentiels -------------------------------------------------------

class ReferentielItem(BaseModel):
    id: str
    nom: str


# --- Dashboard -------------------------------------------------------------------------

class DashboardKPI(BaseModel):
    chiffre_affaires: float
    marge: float
    stock_total_valorise: float
    dettes_creances_en_cours: float
    depenses_mois: float
    nb_boutiques_actives: int
