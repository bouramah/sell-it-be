from fastapi import APIRouter

from app.data.fixtures import PROMOTIONS
from app.models.schemas import Promotion

router = APIRouter(prefix="/api/v1/promotions", tags=["promotions"])


@router.get("", response_model=list[Promotion])
def list_promotions(boutique_id: str | None = None) -> list[Promotion]:
    if boutique_id:
        return [p for p in PROMOTIONS if p.boutique_id == boutique_id or p.boutique_id is None]
    return PROMOTIONS
