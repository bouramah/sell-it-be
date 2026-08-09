from fastapi import APIRouter, HTTPException

from app.data.fixtures import BOUTIQUES, FOURNISSEURS
from app.models.schemas import Boutique, Fournisseur, Secteur, StatutBoutique

router = APIRouter(prefix="/api/v1", tags=["reseau"])


@router.get("/boutiques", response_model=list[Boutique])
def list_boutiques(
    ville: str | None = None,
    secteur: Secteur | None = None,
    statut: StatutBoutique | None = None,
) -> list[Boutique]:
    result = BOUTIQUES
    if ville:
        result = [b for b in result if b.ville.lower() == ville.lower()]
    if secteur:
        result = [b for b in result if secteur in b.secteurs]
    if statut:
        result = [b for b in result if b.statut == statut]
    return result


@router.get("/boutiques/{boutique_id}", response_model=Boutique)
def get_boutique(boutique_id: str) -> Boutique:
    for boutique in BOUTIQUES:
        if boutique.id == boutique_id:
            return boutique
    raise HTTPException(status_code=404, detail="Boutique introuvable")


@router.get("/fournisseurs", response_model=list[Fournisseur])
def list_fournisseurs(secteur: Secteur | None = None) -> list[Fournisseur]:
    if secteur:
        return [f for f in FOURNISSEURS if f.secteur == secteur]
    return FOURNISSEURS
