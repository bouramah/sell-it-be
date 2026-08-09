from pydantic import BaseModel

from fastapi import APIRouter
from app.data.fixtures import DETTES, REMBOURSEMENTS
from app.models.schemas import Remboursement, TiersType

router = APIRouter(prefix="/api/v1/dettes", tags=["dettes"])


class LigneDette(BaseModel):
    id: str
    tiers_nom: str
    boutique_id: str
    montant_initial: float
    solde_restant: float
    echeance: str
    statut: str


@router.get("", response_model=list[LigneDette])
def list_dettes(tiers_type: TiersType | None = None, boutique_id: str | None = None) -> list[LigneDette]:
    rows = DETTES
    if tiers_type:
        rows = [d for d in rows if d.tiers_type == tiers_type]
    if boutique_id:
        rows = [d for d in rows if d.boutique_id == boutique_id]
    return [
        LigneDette(
            id=d.id,
            tiers_nom=d.tiers_nom,
            boutique_id=d.boutique_id,
            montant_initial=d.montant_initial,
            solde_restant=d.solde_restant,
            echeance=d.echeance.isoformat(),
            statut=d.statut,
        )
        for d in rows
    ]


@router.get("/remboursements", response_model=list[Remboursement])
def list_remboursements(dette_id: str | None = None) -> list[Remboursement]:
    if dette_id:
        return [r for r in REMBOURSEMENTS if r.dette_id == dette_id]
    return REMBOURSEMENTS
