from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


# --- Enums ---------------------------------------------------------------

class Secteur(str, Enum):
    habillement = "habillement"
    alimentation_generale = "alimentation_generale"
    electronique_electromenager = "electronique_electromenager"


class StatutBoutique(str, Enum):
    active = "active"
    fermee = "fermee"
    en_creation = "en_creation"


class Role(str, Enum):
    vendeur = "vendeur"
    caissier = "caissier"
    gerant = "gerant"
    responsable_achats = "responsable_achats"
    administrateur = "administrateur"


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
    secteurs: list[Secteur]
    quartier: str
    commune: str
    ville: str
    horaires: str
    responsable: str
    statut: StatutBoutique
    telephone: str


class Fournisseur(BaseModel):
    id: str
    nom: str
    secteur: Secteur
    conditions_paiement: str
    contact: str


class Utilisateur(BaseModel):
    id: str
    nom: str
    prenom: str
    contact: str
    role: Role
    boutique_ids: list[str]
    statut: str
    derniere_connexion: datetime | None = None


class PermissionLigne(BaseModel):
    module_action: str
    droits: dict[Role, DroitAcces]


# --- Clients & paiements ----------------------------------------------------

class Client(BaseModel):
    id: str
    nom: str
    contact: str
    boutique_id: str
    segment: SegmentClient
    credit_autorise: bool
    solde_dette: float


class PaiementClient(BaseModel):
    id: str
    client_nom: str
    reference: str  # commande liée ou "Dette — remboursement"
    boutique_id: str
    mode_paiement: ModePaiement
    date: date
    montant: float
    statut: StatutPaiement


class PaiementFournisseur(BaseModel):
    id: str
    fournisseur_nom: str
    reference: str
    boutique_id: str
    mode_paiement: ModePaiement
    date: date
    montant: float
    statut: StatutPaiement
    document_url: str | None = None


# --- Produits & stock --------------------------------------------------------

class Produit(BaseModel):
    id: str
    nom: str
    secteur: Secteur
    categorie: str
    prix: float
    unite: str
    code_barres: str
    date_peremption: date | None = None
    image_url: str | None = None


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


# --- Commandes ----------------------------------------------------------------

class CommandeClient(BaseModel):
    id: str
    client_nom: str
    boutique_id: str
    canal: CanalCommande
    mode_paiement: ModePaiement
    montant: float
    statut: StatutCommandeClient
    date_creation: datetime


class ArticleCommande(BaseModel):
    id: str
    produit_id: str
    produit_nom: str
    quantite: int
    prix_unitaire: float


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


class ArticleCommandeFournisseur(ArticleCommande):
    quantite_recue: int


class CommandeFournisseurDetail(LigneCommandeFournisseur):
    articles: list[ArticleCommandeFournisseur]


# --- Livraisons ---------------------------------------------------------------

class Livraison(BaseModel):
    id: str
    commande_id: str
    livreur: str
    boutique_id: str
    adresse: str
    creneau: str
    statut: StatutLivraison
    preuve_disponible: bool


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


# --- Transferts de stock -----------------------------------------------------------

class TransfertStock(BaseModel):
    id: str
    produit_id: str
    boutique_source_id: str
    boutique_destination_id: str
    quantite: int
    demandeur: str
    statut: StatutTransfert


# --- Comptabilité ------------------------------------------------------------------

class CompteResultatBoutique(BaseModel):
    boutique_id: str
    chiffre_affaires: float
    achats: float
    depenses: float
    marge_nette: float


# --- Promotions & tarifs ------------------------------------------------------------

class Promotion(BaseModel):
    id: str
    nom: str
    boutique_id: str | None
    secteur: Secteur | None
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
    id: str
    horodatage: datetime
    action: str
    auteur: str
    boutique_id: str | None


class ParametreSecurite(BaseModel):
    label: str
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
