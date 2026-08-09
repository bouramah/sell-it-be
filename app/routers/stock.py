from pydantic import BaseModel

from fastapi import APIRouter
from app.data.fixtures import ECARTS_INVENTAIRE, MOUVEMENTS_STOCK, PRODUITS, STOCKS
from app.models.schemas import MotifMouvementStock, Secteur, StatutEcartInventaire

router = APIRouter(prefix="/api/v1/stock", tags=["stock"])


class LigneStock(BaseModel):
    boutique_id: str
    produit_id: str
    produit_nom: str
    secteur: Secteur
    quantite_disponible: int
    quantite_reservee: int
    seuil_alerte: int
    statut: str
    derniere_mouvement: str


class LigneMouvementStock(BaseModel):
    id: str
    horodatage: str
    produit_id: str
    produit_nom: str
    boutique_id: str
    motif: MotifMouvementStock
    operateur: str
    quantite: int


class LigneEcartInventaire(BaseModel):
    id: str
    produit_id: str
    produit_nom: str
    boutique_id: str
    theorique: int
    reel: int
    ecart: int
    statut: StatutEcartInventaire


def _statut_stock(disponible: int, seuil: int) -> str:
    if disponible <= seuil * 0.5:
        return "critique"
    if disponible <= seuil:
        return "a_surveiller"
    return "correct"


@router.get("", response_model=list[LigneStock])
def list_stock(boutique_id: str | None = None, secteur: Secteur | None = None) -> list[LigneStock]:
    produits_by_id = {p.id: p for p in PRODUITS}
    rows = STOCKS
    if boutique_id:
        rows = [s for s in rows if s.boutique_id == boutique_id]
    if secteur:
        rows = [s for s in rows if produits_by_id[s.produit_id].secteur == secteur]
    return [
        LigneStock(
            boutique_id=s.boutique_id,
            produit_id=s.produit_id,
            produit_nom=produits_by_id[s.produit_id].nom,
            secteur=produits_by_id[s.produit_id].secteur,
            quantite_disponible=s.quantite_disponible,
            quantite_reservee=s.quantite_reservee,
            seuil_alerte=s.seuil_alerte,
            statut=_statut_stock(s.quantite_disponible, s.seuil_alerte),
            derniere_mouvement=s.derniere_mouvement.isoformat(),
        )
        for s in rows
    ]


@router.get("/mouvements", response_model=list[LigneMouvementStock])
def list_mouvements(boutique_id: str | None = None) -> list[LigneMouvementStock]:
    produits_by_id = {p.id: p for p in PRODUITS}
    rows = MOUVEMENTS_STOCK
    if boutique_id:
        rows = [m for m in rows if m.boutique_id == boutique_id]
    rows = sorted(rows, key=lambda m: m.horodatage, reverse=True)
    return [
        LigneMouvementStock(
            id=m.id,
            horodatage=m.horodatage.isoformat(),
            produit_id=m.produit_id,
            produit_nom=produits_by_id[m.produit_id].nom,
            boutique_id=m.boutique_id,
            motif=m.motif,
            operateur=m.operateur,
            quantite=m.quantite,
        )
        for m in rows
    ]


@router.get("/inventaire", response_model=list[LigneEcartInventaire])
def list_inventaire(boutique_id: str | None = None) -> list[LigneEcartInventaire]:
    produits_by_id = {p.id: p for p in PRODUITS}
    rows = ECARTS_INVENTAIRE
    if boutique_id:
        rows = [e for e in rows if e.boutique_id == boutique_id]
    return [
        LigneEcartInventaire(
            id=e.id,
            produit_id=e.produit_id,
            produit_nom=produits_by_id[e.produit_id].nom,
            boutique_id=e.boutique_id,
            theorique=e.theorique,
            reel=e.reel,
            ecart=e.reel - e.theorique,
            statut=e.statut,
        )
        for e in rows
    ]
