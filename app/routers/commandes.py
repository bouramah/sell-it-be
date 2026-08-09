from fastapi import APIRouter

from app.data.fixtures import COMMANDES_CLIENTS, COMMANDES_FOURNISSEURS
from app.models.schemas import CommandeClient, LigneCommandeFournisseur

router = APIRouter(prefix="/api/v1", tags=["commandes"])


@router.get("/commandes-clients", response_model=list[CommandeClient])
def list_commandes_clients(boutique_id: str | None = None) -> list[CommandeClient]:
    if boutique_id:
        return [c for c in COMMANDES_CLIENTS if c.boutique_id == boutique_id]
    return COMMANDES_CLIENTS


@router.get("/commandes-fournisseurs", response_model=list[LigneCommandeFournisseur])
def list_commandes_fournisseurs(boutique_id: str | None = None) -> list[LigneCommandeFournisseur]:
    if boutique_id:
        return [c for c in COMMANDES_FOURNISSEURS if c.boutique_id == boutique_id]
    return COMMANDES_FOURNISSEURS
