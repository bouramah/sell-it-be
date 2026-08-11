from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import JournalAuditDB, ParametreSecuriteDB, UtilisateurDB
from app.models.schemas import JournalAuditEntry, ParametreSecurite
from app.models.write_schemas import ParametreSecuriteUpdate
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/securite", tags=["securite"])


@router.get("/audit", response_model=list[JournalAuditEntry])
def journal_audit(boutique_id: str | None = None, db: Session = Depends(get_db)) -> list[JournalAuditDB]:
    query = db.query(JournalAuditDB)
    if boutique_id:
        query = query.filter(JournalAuditDB.boutique_id == boutique_id)
    return sorted(query.all(), key=lambda a: a.horodatage, reverse=True)


@router.get("/parametres", response_model=list[ParametreSecurite])
def parametres_securite(db: Session = Depends(get_db)) -> list[ParametreSecuriteDB]:
    return sorted(db.query(ParametreSecuriteDB).all(), key=lambda p: p.ordre)


@router.put("/parametres/{parametre_id}", response_model=ParametreSecurite)
def modifier_parametre_securite(
    parametre_id: str,
    payload: ParametreSecuriteUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ParametreSecuriteDB:
    p = db.get(ParametreSecuriteDB, parametre_id)
    if not p:
        raise HTTPException(status_code=404, detail="Paramètre introuvable")
    p.actif = payload.actif
    log_audit(
        db,
        f"Paramètre de sécurité { 'activé' if payload.actif else 'désactivé' } — {p.label}",
        f"{current_user.prenom} {current_user.nom}",
    )
    db.commit()
    db.refresh(p)
    return p
