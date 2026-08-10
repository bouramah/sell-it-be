import uuid
from datetime import date

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import DetteDB, RemboursementDB
from app.models.schemas import Remboursement, StatutDette, TiersType
from app.models.write_schemas import DetteCreate, RemboursementCreate

router = APIRouter(prefix="/api/v1/dettes", tags=["dettes"])


class LigneDette(BaseModel):
    id: str
    tiers_nom: str
    boutique_id: str
    montant_initial: float
    solde_restant: float
    echeance: str
    statut: str


def _to_ligne(d: DetteDB) -> LigneDette:
    return LigneDette(
        id=d.id,
        tiers_nom=d.tiers_nom,
        boutique_id=d.boutique_id,
        montant_initial=d.montant_initial,
        solde_restant=d.solde_restant,
        echeance=d.echeance.isoformat(),
        statut=d.statut,
    )


@router.get("", response_model=list[LigneDette])
def list_dettes(tiers_type: TiersType | None = None, boutique_id: str | None = None, db: Session = Depends(get_db)) -> list[LigneDette]:
    query = db.query(DetteDB)
    if tiers_type:
        query = query.filter(DetteDB.tiers_type == tiers_type)
    if boutique_id:
        query = query.filter(DetteDB.boutique_id == boutique_id)
    return [_to_ligne(d) for d in query.all()]


@router.post("", response_model=LigneDette, status_code=201)
def create_dette(
    payload: DetteCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> LigneDette:
    d = DetteDB(
        id=str(uuid.uuid4())[:8],
        tiers_type=payload.tiers_type,
        tiers_nom=payload.tiers_nom,
        boutique_id=payload.boutique_id,
        montant_initial=payload.montant_initial,
        solde_restant=payload.montant_initial,
        echeance=payload.echeance,
        statut=StatutDette.en_cours,
    )
    db.add(d)
    db.commit()
    return _to_ligne(d)


@router.get("/remboursements", response_model=list[Remboursement])
def list_remboursements(dette_id: str | None = None, db: Session = Depends(get_db)) -> list[RemboursementDB]:
    query = db.query(RemboursementDB)
    if dette_id:
        query = query.filter(RemboursementDB.dette_id == dette_id)
    return query.all()


@router.post("/{dette_id}/remboursements", response_model=LigneDette, status_code=201)
def encaisser_remboursement(
    dette_id: str,
    payload: RemboursementCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> LigneDette:
    d = db.get(DetteDB, dette_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dette introuvable")
    if payload.montant > d.solde_restant:
        raise HTTPException(status_code=400, detail="Le montant dépasse le solde restant")

    r = RemboursementDB(
        id=str(uuid.uuid4())[:8],
        dette_id=dette_id,
        montant=payload.montant,
        mode_paiement=payload.mode_paiement,
        date=date.today(),
        operateur=payload.operateur,
    )
    db.add(r)

    d.solde_restant -= payload.montant
    d.statut = StatutDette.soldee if d.solde_restant <= 0 else StatutDette.en_cours
    db.commit()
    return _to_ligne(d)
