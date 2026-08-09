from fastapi import APIRouter

from app.data.fixtures import CLIENTS, PAIEMENTS_CLIENTS, PAIEMENTS_FOURNISSEURS
from app.models.schemas import Client, PaiementClient, PaiementFournisseur

router = APIRouter(prefix="/api/v1", tags=["clients"])


@router.get("/clients", response_model=list[Client])
def list_clients(boutique_id: str | None = None) -> list[Client]:
    if boutique_id:
        return [c for c in CLIENTS if c.boutique_id == boutique_id]
    return CLIENTS


@router.get("/paiements-clients", response_model=list[PaiementClient])
def list_paiements_clients(boutique_id: str | None = None) -> list[PaiementClient]:
    if boutique_id:
        return [p for p in PAIEMENTS_CLIENTS if p.boutique_id == boutique_id]
    return PAIEMENTS_CLIENTS


@router.get("/paiements-fournisseurs", response_model=list[PaiementFournisseur])
def list_paiements_fournisseurs(boutique_id: str | None = None) -> list[PaiementFournisseur]:
    if boutique_id:
        return [p for p in PAIEMENTS_FOURNISSEURS if p.boutique_id == boutique_id]
    return PAIEMENTS_FOURNISSEURS
