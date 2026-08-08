from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


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


class Boutique(BaseModel):
    id: str
    nom: str
    secteurs: list[Secteur]
    quartier: str
    commune: str
    ville: str
    adresse: str
    statut: StatutBoutique
    responsable: str
    horaires: str
    telephone: str


class Utilisateur(BaseModel):
    id: str
    nom: str
    prenom: str
    contact: str
    role: Role
    boutique_ids: list[str]
    statut: str
    derniere_connexion: datetime | None = None


class Produit(BaseModel):
    id: str
    nom: str
    secteur: Secteur
    categorie: str
    prix: float
    unite: str
    code_barres: str
    date_peremption: date | None = None


class StockBoutique(BaseModel):
    boutique_id: str
    produit_id: str
    quantite_disponible: int
    quantite_reservee: int
    seuil_alerte: int
    derniere_mouvement: datetime


class DroitAcces(str, Enum):
    complet = "complet"
    lecture_seule = "lecture_seule"
    partiel = "partiel"
    aucun = "aucun"


class PermissionLigne(BaseModel):
    module_action: str
    droits: dict[Role, DroitAcces]


class DashboardKPI(BaseModel):
    chiffre_affaires: float
    marge: float
    stock_total_valorise: float
    dettes_creances_en_cours: float
    depenses_mois: float
    nb_boutiques_actives: int
