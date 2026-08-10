import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import CommandeClientDB, CommandeFournisseurDB
from app.models.schemas import CommandeClient, LigneCommandeFournisseur
from app.models.write_schemas import (
    CommandeClientCreate,
    CommandeClientUpdate,
    CommandeFournisseurCreate,
    CommandeFournisseurUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["commandes"])


@router.get("/commandes-clients", response_model=list[CommandeClient])
def list_commandes_clients(boutique_id: str | None = None, db: Session = Depends(get_db)) -> list[CommandeClientDB]:
    query = db.query(CommandeClientDB)
    if boutique_id:
        query = query.filter(CommandeClientDB.boutique_id == boutique_id)
    return query.all()


@router.post("/commandes-clients", response_model=CommandeClient, status_code=201)
def create_commande_client(
    payload: CommandeClientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> CommandeClientDB:
    c = CommandeClientDB(id=str(uuid.uuid4())[:8], **payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/commandes-clients/{commande_id}", response_model=CommandeClient)
def update_commande_client(
    commande_id: str,
    payload: CommandeClientUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> CommandeClientDB:
    c = db.get(CommandeClientDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return c


@router.get("/commandes-fournisseurs", response_model=list[LigneCommandeFournisseur])
def list_commandes_fournisseurs(boutique_id: str | None = None, db: Session = Depends(get_db)) -> list[CommandeFournisseurDB]:
    query = db.query(CommandeFournisseurDB)
    if boutique_id:
        query = query.filter(CommandeFournisseurDB.boutique_id == boutique_id)
    return query.all()


@router.post("/commandes-fournisseurs", response_model=LigneCommandeFournisseur, status_code=201)
def create_commande_fournisseur(
    payload: CommandeFournisseurCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> CommandeFournisseurDB:
    c = CommandeFournisseurDB(id=str(uuid.uuid4())[:8], **payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/commandes-fournisseurs/{commande_id}", response_model=LigneCommandeFournisseur)
def update_commande_fournisseur(
    commande_id: str,
    payload: CommandeFournisseurUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> CommandeFournisseurDB:
    c = db.get(CommandeFournisseurDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return c
