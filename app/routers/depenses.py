from fastapi import APIRouter

from app.data.fixtures import DEPENSES
from app.models.schemas import Depense

router = APIRouter(prefix="/api/v1/depenses", tags=["depenses"])


@router.get("", response_model=list[Depense])
def list_depenses(boutique_id: str | None = None) -> list[Depense]:
    if boutique_id:
        return [d for d in DEPENSES if d.boutique_id == boutique_id]
    return DEPENSES
