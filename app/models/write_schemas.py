from datetime import date

from pydantic import BaseModel

from app.models.schemas import Role, Secteur, StatutBoutique


class BoutiqueCreate(BaseModel):
    nom: str
    secteurs: list[Secteur]
    quartier: str
    commune: str
    ville: str
    horaires: str
    responsable: str
    statut: StatutBoutique = StatutBoutique.en_creation
    telephone: str


class BoutiqueUpdate(BaseModel):
    nom: str | None = None
    secteurs: list[Secteur] | None = None
    quartier: str | None = None
    commune: str | None = None
    ville: str | None = None
    horaires: str | None = None
    responsable: str | None = None
    statut: StatutBoutique | None = None
    telephone: str | None = None


class UtilisateurCreate(BaseModel):
    nom: str
    prenom: str
    contact: str
    mot_de_passe: str | None = None
    role: Role
    boutique_ids: list[str] = []
    statut: str = "actif"


class UtilisateurUpdate(BaseModel):
    nom: str | None = None
    prenom: str | None = None
    contact: str | None = None
    mot_de_passe: str | None = None
    role: Role | None = None
    boutique_ids: list[str] | None = None
    statut: str | None = None


class ProduitCreate(BaseModel):
    nom: str
    secteur: Secteur
    categorie: str
    prix: float
    unite: str
    code_barres: str
    date_peremption: date | None = None


class ProduitUpdate(BaseModel):
    nom: str | None = None
    secteur: Secteur | None = None
    categorie: str | None = None
    prix: float | None = None
    unite: str | None = None
    code_barres: str | None = None
    date_peremption: date | None = None


class ReferentielCreate(BaseModel):
    nom: str


class ReferentielUpdate(BaseModel):
    nom: str


class LoginRequest(BaseModel):
    contact: str
    mot_de_passe: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UtilisateurConnecte(BaseModel):
    id: str
    nom: str
    prenom: str
    contact: str
    role: Role
    boutique_ids: list[str]
