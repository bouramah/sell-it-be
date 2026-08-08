from pydantic import BaseModel

from fastapi import APIRouter
from app.data.fixtures import PRODUITS, STOCKS

router = APIRouter(prefix="/api/v1/stock", tags=["stock"])


class LigneStock(BaseModel):
    boutique_id: str
    produit_id: str
    produit_nom: str
    quantite_disponible: int
    quantite_reservee: int
    seuil_alerte: int
    en_alerte: bool
    derniere_mouvement: str


@router.get("", response_model=list[LigneStock])
def list_stock(boutique_id: str | None = None) -> list[LigneStock]:
    produits_by_id = {p.id: p for p in PRODUITS}
    rows = STOCKS if boutique_id is None else [s for s in STOCKS if s.boutique_id == boutique_id]
    return [
        LigneStock(
            boutique_id=s.boutique_id,
            produit_id=s.produit_id,
            produit_nom=produits_by_id[s.produit_id].nom,
            quantite_disponible=s.quantite_disponible,
            quantite_reservee=s.quantite_reservee,
            seuil_alerte=s.seuil_alerte,
            en_alerte=s.quantite_disponible <= s.seuil_alerte,
            derniere_mouvement=s.derniere_mouvement.isoformat(),
        )
        for s in rows
    ]
