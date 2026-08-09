from fastapi import APIRouter, HTTPException

from app.data.fixtures import REFERENTIELS
from app.models.schemas import ReferentielItem

router = APIRouter(prefix="/api/v1/parametres", tags=["parametres"])


@router.get("/referentiels", response_model=dict[str, list[ReferentielItem]])
def list_referentiels() -> dict[str, list[ReferentielItem]]:
    return REFERENTIELS


@router.get("/referentiels/{categorie}", response_model=list[ReferentielItem])
def get_referentiel(categorie: str) -> list[ReferentielItem]:
    if categorie not in REFERENTIELS:
        raise HTTPException(status_code=404, detail="Référentiel introuvable")
    return REFERENTIELS[categorie]
