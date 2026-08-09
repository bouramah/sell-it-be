from fastapi import APIRouter

from app.data.fixtures import LIVRAISONS
from app.models.schemas import Livraison

router = APIRouter(prefix="/api/v1/livraisons", tags=["livraisons"])


@router.get("", response_model=list[Livraison])
def list_livraisons(boutique_id: str | None = None) -> list[Livraison]:
    if boutique_id:
        return [l for l in LIVRAISONS if l.boutique_id == boutique_id]
    return LIVRAISONS
