import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import ProduitDB
from app.models.schemas import Produit, Secteur
from app.models.write_schemas import ProduitCreate, ProduitUpdate

router = APIRouter(prefix="/api/v1/produits", tags=["produits"])


@router.get("", response_model=list[Produit])
def list_produits(q: str | None = None, secteur: Secteur | None = None, db: Session = Depends(get_db)) -> list[ProduitDB]:
    query = db.query(ProduitDB)
    if secteur:
        query = query.filter(ProduitDB.secteur == secteur)
    if q:
        query = query.filter(ProduitDB.nom.ilike(f"%{q}%"))
    return query.all()


@router.post("", response_model=Produit, status_code=201)
def create_produit(
    payload: ProduitCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProduitDB:
    if db.query(ProduitDB).filter(ProduitDB.code_barres == payload.code_barres).first():
        raise HTTPException(status_code=409, detail="Un produit avec ce code-barres existe déjà")
    p = ProduitDB(id=str(uuid.uuid4())[:8], **payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.put("/{produit_id}", response_model=Produit)
def update_produit(
    produit_id: str,
    payload: ProduitUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProduitDB:
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{produit_id}", status_code=204)
def delete_produit(
    produit_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    db.delete(p)
    db.commit()
