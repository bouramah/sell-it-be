from datetime import date

from pydantic import BaseModel

from app.models.schemas import (
    CanalCommande,
    DroitAcces,
    MotifMouvementStock,
    ModePaiement,
    PalierPrix,
    SegmentClient,
    StatutBoutique,
    StatutCaisse,
    StatutCommandeClient,
    StatutCommandeFournisseur,
    StatutDette,
    StatutEcartInventaire,
    StatutLivraison,
    StatutPromotion,
    StatutTransfert,
    TiersType,
    TypeMouvementCaisse,
)


class BoutiqueCreate(BaseModel):
    nom: str
    secteurs: list[str]
    quartier: str
    commune: str
    ville: str
    horaires: str
    responsable: str
    statut: StatutBoutique = StatutBoutique.en_creation
    telephone: str
    latitude: float | None = None
    longitude: float | None = None
    secteur_geo_id: str | None = None


class BoutiqueUpdate(BaseModel):
    nom: str | None = None
    secteurs: list[str] | None = None
    quartier: str | None = None
    commune: str | None = None
    ville: str | None = None
    horaires: str | None = None
    responsable: str | None = None
    statut: StatutBoutique | None = None
    telephone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    secteur_geo_id: str | None = None


class UtilisateurCreate(BaseModel):
    nom: str
    prenom: str
    contact: str
    mot_de_passe: str | None = None
    role: str
    boutique_ids: list[str] = []
    statut: str = "actif"
    secteur_geo_id: str | None = None


class UtilisateurUpdate(BaseModel):
    nom: str | None = None
    prenom: str | None = None
    contact: str | None = None
    mot_de_passe: str | None = None
    role: str | None = None
    boutique_ids: list[str] | None = None
    statut: str | None = None
    secteur_geo_id: str | None = None


class ProduitCreate(BaseModel):
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


class ProduitUpdate(BaseModel):
    # Pas de champs de prix ici : un changement de prix doit obligatoirement passer par
    # POST /produits/{id}/prix-periodes (période datée, traçable, sans chevauchement).
    nom: str | None = None
    secteur: str | None = None
    categorie: str | None = None
    seuil_semi_gros: int | None = None
    seuil_gros: int | None = None
    unite: str | None = None
    code_barres: str | None = None
    date_peremption: date | None = None


class PrixPeriodeInput(BaseModel):
    boutique_id: str | None = None  # None = prix de référence réseau
    palier: PalierPrix
    prix: float
    date_debut: date
    date_fin: date | None = None


class PrixAchatInput(BaseModel):
    fournisseur_id: str
    palier: PalierPrix
    prix: float
    date_debut: date
    date_fin: date | None = None


class FournisseurCreate(BaseModel):
    nom: str
    secteur: str
    conditions_paiement: str
    contact: str
    secteur_geo_id: str | None = None


class FournisseurUpdate(BaseModel):
    nom: str | None = None
    secteur: str | None = None
    conditions_paiement: str | None = None
    contact: str | None = None
    secteur_geo_id: str | None = None


class ClientCreate(BaseModel):
    nom: str
    contact: str
    boutique_ids: list[str]
    segment: SegmentClient = SegmentClient.nouveau
    credit_autorise: bool = False
    quartier: str | None = None
    commune: str | None = None
    ville: str | None = None
    secteur_geo_id: str | None = None


class ClientUpdate(BaseModel):
    nom: str | None = None
    contact: str | None = None
    boutique_ids: list[str] | None = None
    segment: SegmentClient | None = None
    credit_autorise: bool | None = None
    quartier: str | None = None
    commune: str | None = None
    ville: str | None = None
    secteur_geo_id: str | None = None


class RegionInput(BaseModel):
    nom: str


class VilleInput(BaseModel):
    nom: str
    region_id: str


class CommuneInput(BaseModel):
    nom: str
    ville_id: str


class QuartierGeoInput(BaseModel):
    nom: str
    commune_id: str


class SecteurGeoInput(BaseModel):
    nom: str
    quartier_id: str


class StockLigneCreate(BaseModel):
    boutique_id: str
    produit_id: str
    quantite_disponible: int = 0
    quantite_reservee: int = 0
    seuil_alerte: int = 0


class StockLigneUpdate(BaseModel):
    quantite_disponible: int | None = None
    quantite_reservee: int | None = None
    seuil_alerte: int | None = None


class MouvementStockCreate(BaseModel):
    produit_id: str
    boutique_id: str
    motif: MotifMouvementStock
    operateur: str = ""
    quantite: int  # signé : positif = entrée, négatif = sortie


class EcartInventaireCreate(BaseModel):
    produit_id: str
    boutique_id: str
    theorique: int
    reel: int


class EcartInventaireUpdate(BaseModel):
    statut: StatutEcartInventaire


class CaisseCreate(BaseModel):
    boutique_id: str
    libelle: str
    fond_initial: float
    operateur: str = ""


class MouvementCaisseCreate(BaseModel):
    caisse_id: str
    type: TypeMouvementCaisse
    motif: str
    operateur: str = ""
    montant: float  # positif, le signe est dérivé du type


class CaisseFermeture(BaseModel):
    solde_reel: float


class ArticleCommandeInput(BaseModel):
    produit_id: str
    quantite: int
    palier: PalierPrix = PalierPrix.detail  # détermine le prix catalogue de repli et la base de calcul de la remise
    prix_unitaire: float | None = None  # si absent, reprend le prix catalogue du produit pour ce palier (et cette boutique)


class CommandeClientCreate(BaseModel):
    client_nom: str
    boutique_id: str
    canal: CanalCommande
    mode_paiement: ModePaiement
    statut: StatutCommandeClient = StatutCommandeClient.en_attente
    articles: list[ArticleCommandeInput]
    remise_motif: str | None = None  # obligatoire côté serveur si la remise dépasse le seuil (cf. SEUIL_REMISE)


class CommandeClientUpdate(BaseModel):
    statut: StatutCommandeClient | None = None
    client_nom: str | None = None
    canal: CanalCommande | None = None
    mode_paiement: ModePaiement | None = None
    articles: list[ArticleCommandeInput] | None = None
    remise_motif: str | None = None


class CommandeFournisseurCreate(BaseModel):
    fournisseur_id: str
    boutique_id: str
    date_attendue: date
    statut: StatutCommandeFournisseur = StatutCommandeFournisseur.brouillon
    articles: list[ArticleCommandeInput]


class CommandeFournisseurUpdate(BaseModel):
    statut: StatutCommandeFournisseur | None = None
    date_attendue: date | None = None
    fournisseur_id: str | None = None
    articles: list[ArticleCommandeInput] | None = None


class CorrectionReceptionLigne(BaseModel):
    produit_id: str
    quantite_recue: int


class CorrectionReceptionCreate(BaseModel):
    operateur: str
    lignes: list[CorrectionReceptionLigne]
    date_attendue: date | None = None


class ReceptionLigne(BaseModel):
    produit_id: str
    quantite: int


class ReceptionCreate(BaseModel):
    operateur: str
    lignes: list[ReceptionLigne]


class DetteCreate(BaseModel):
    tiers_type: TiersType
    tiers_nom: str
    boutique_id: str
    montant_initial: float
    echeance: date


class RemboursementCreate(BaseModel):
    caisse_id: str
    montant: float
    mode_paiement: ModePaiement
    operateur: str


class TransfertCreate(BaseModel):
    produit_id: str
    boutique_source_id: str
    boutique_destination_id: str
    quantite: int
    demandeur: str


class TransfertStatutUpdate(BaseModel):
    statut: StatutTransfert
    # Utilisé seulement pour statut='recu' — si absent, on suppose que tout est arrivé
    # (quantite_recue = quantite demandée). motif_ecart obligatoire si quantite_recue < quantite.
    quantite_recue: int | None = None
    motif_ecart: str | None = None


class LivraisonCreate(BaseModel):
    commande_id: str
    livreur: str = ""
    livreur_user_id: str | None = None
    boutique_id: str
    adresse: str
    creneau: str


class LivraisonStatutUpdate(BaseModel):
    statut: StatutLivraison


class DepenseCreate(BaseModel):
    boutique_id: str
    caisse_id: str
    categorie: str
    auteur: str = ""
    date: date
    montant: float


class PaiementClientCreate(BaseModel):
    client_nom: str = ""
    commande_id: str | None = None
    boutique_id: str
    caisse_id: str
    mode_paiement: ModePaiement
    montant: float
    date_paiement: date | None = None


class PaiementFournisseurCreate(BaseModel):
    fournisseur_nom: str
    commande_id: str | None = None
    boutique_id: str
    caisse_id: str
    mode_paiement: ModePaiement
    montant: float
    date_paiement: date | None = None


class PaiementCaisseInput(BaseModel):
    caisse_id: str


class PromotionCreate(BaseModel):
    nom: str
    boutique_id: str | None = None
    secteur: str | None = None
    impact_estime: str


class PromotionStatutUpdate(BaseModel):
    statut: StatutPromotion


class PermissionUpdate(BaseModel):
    module_action: str
    role: str
    droit: DroitAcces


class ReferentielCreate(BaseModel):
    nom: str


class ReferentielUpdate(BaseModel):
    nom: str


class RoleCreate(BaseModel):
    id: str
    libelle: str
    portee: str


class RoleUpdate(BaseModel):
    libelle: str | None = None
    portee: str | None = None


class ParametreSecuriteUpdate(BaseModel):
    actif: bool


class LoginRequest(BaseModel):
    contact: str
    mot_de_passe: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MotDePasseOublieRequest(BaseModel):
    contact: str


class ReinitialisationMotDePasseRequest(BaseModel):
    contact: str
    code: str
    nouveau_mot_de_passe: str


class PushTokenUpdate(BaseModel):
    push_token: str | None = None


class ChangementMotDePasseRequest(BaseModel):
    mot_de_passe_actuel: str
    nouveau_mot_de_passe: str


class UtilisateurConnecte(BaseModel):
    id: str
    nom: str
    prenom: str
    contact: str
    role: str
    boutique_ids: list[str]
