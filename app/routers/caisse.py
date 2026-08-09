from pydantic import BaseModel

from fastapi import APIRouter
from app.data.fixtures import CAISSES, MOUVEMENTS_CAISSE
from app.models.schemas import Caisse, TypeMouvementCaisse

router = APIRouter(prefix="/api/v1/caisse", tags=["caisse"])


class LigneMouvementCaisse(BaseModel):
    id: str
    horodatage: str
    boutique_id: str
    caisse_libelle: str
    type: TypeMouvementCaisse
    motif: str
    operateur: str
    montant: float


@router.get("/caisses", response_model=list[Caisse])
def list_caisses(boutique_id: str | None = None) -> list[Caisse]:
    if boutique_id:
        return [c for c in CAISSES if c.boutique_id == boutique_id]
    return CAISSES


@router.get("/mouvements", response_model=list[LigneMouvementCaisse])
def list_mouvements_caisse(boutique_id: str | None = None) -> list[LigneMouvementCaisse]:
    rows = MOUVEMENTS_CAISSE
    if boutique_id:
        rows = [m for m in rows if m.boutique_id == boutique_id]
    rows = sorted(rows, key=lambda m: m.horodatage)
    return [
        LigneMouvementCaisse(
            id=m.id,
            horodatage=m.horodatage.isoformat(),
            boutique_id=m.boutique_id,
            caisse_libelle=m.caisse_libelle,
            type=m.type,
            motif=m.motif,
            operateur=m.operateur,
            montant=m.montant,
        )
        for m in rows
    ]
