import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import DepenseDB
from app.models.schemas import Depense, StatutValidationDepense
from app.models.write_schemas import DepenseCreate

router = APIRouter(prefix="/api/v1/depenses", tags=["depenses"])

# Au-delà de ce montant, une dépense doit être validée par le siège (double validation, cf. CDC anti-fraude).
SEUIL_VALIDATION_SIEGE = 500_000


@router.get("", response_model=list[Depense])
def list_depenses(boutique_id: str | None = None, db: Session = Depends(get_db)) -> list[DepenseDB]:
    query = db.query(DepenseDB)
    if boutique_id:
        query = query.filter(DepenseDB.boutique_id == boutique_id)
    return query.all()


@router.post("", response_model=Depense, status_code=201)
def create_depense(
    payload: DepenseCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> DepenseDB:
    statut = (
        StatutValidationDepense.auto_validee
        if payload.montant < SEUIL_VALIDATION_SIEGE
        else StatutValidationDepense.en_attente
    )
    d = DepenseDB(
        id=str(uuid.uuid4())[:8], boutique_id=payload.boutique_id, categorie=payload.categorie,
        auteur=payload.auteur, date=payload.date, montant=payload.montant,
        statut_validation=statut, justificatif_disponible=payload.justificatif_disponible,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@router.post("/{depense_id}/valider", response_model=Depense)
def valider_depense(
    depense_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> DepenseDB:
    d = db.get(DepenseDB, depense_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dépense introuvable")
    if d.statut_validation != StatutValidationDepense.en_attente:
        raise HTTPException(status_code=400, detail="Cette dépense n'est pas en attente de validation")
    d.statut_validation = StatutValidationDepense.validee_siege
    db.commit()
    db.refresh(d)
    return d
