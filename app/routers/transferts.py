from fastapi import APIRouter

from app.data.fixtures import TRANSFERTS
from app.models.schemas import TransfertStock

router = APIRouter(prefix="/api/v1/transferts", tags=["transferts"])


@router.get("", response_model=list[TransfertStock])
def list_transferts(boutique_id: str | None = None) -> list[TransfertStock]:
    if boutique_id:
        return [
            t for t in TRANSFERTS
            if t.boutique_source_id == boutique_id or t.boutique_destination_id == boutique_id
        ]
    return TRANSFERTS
