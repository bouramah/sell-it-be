import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_user
from app.data.fixtures import PAIEMENTS_CLIENTS, PAIEMENTS_FOURNISSEURS
from app.db_models.models import ClientDB, DetteDB
from app.models.schemas import Client, PaiementClient, PaiementFournisseur, TiersType
from app.models.write_schemas import ClientCreate, ClientUpdate

router = APIRouter(prefix="/api/v1", tags=["clients"])


def _solde_dette(db: Session, client_nom: str) -> float:
    total = (
        db.query(func.coalesce(func.sum(DetteDB.solde_restant), 0.0))
        .filter(DetteDB.tiers_type == TiersType.client, DetteDB.tiers_nom == client_nom)
        .scalar()
    )
    return float(total or 0.0)


def _to_schema(c: ClientDB, db: Session) -> Client:
    return Client(
        id=c.id,
        nom=c.nom,
        contact=c.contact,
        boutique_id=c.boutique_id,
        segment=c.segment,
        credit_autorise=c.credit_autorise,
        solde_dette=_solde_dette(db, c.nom),
    )


@router.get("/clients", response_model=list[Client])
def list_clients(boutique_id: str | None = None, db: Session = Depends(get_db)) -> list[Client]:
    query = db.query(ClientDB)
    if boutique_id:
        query = query.filter(ClientDB.boutique_id == boutique_id)
    return [_to_schema(c, db) for c in query.all()]


@router.post("/clients", response_model=Client, status_code=201)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Client:
    c = ClientDB(id=str(uuid.uuid4())[:8], **payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_schema(c, db)


@router.put("/clients/{client_id}", response_model=Client)
def update_client(
    client_id: str,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Client:
    c = db.get(ClientDB, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return _to_schema(c, db)


@router.delete("/clients/{client_id}", status_code=204)
def delete_client(
    client_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    c = db.get(ClientDB, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client introuvable")
    db.delete(c)
    db.commit()


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
