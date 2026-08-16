from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import SECURITE_GESTION
from app.core.security import get_current_user
from app.db_models.models import JournalAuditDB, ParametreSecuriteDB, UtilisateurDB
from app.models.schemas import JournalAuditEntry, JournalAuditPage, ParametreSecurite
from app.models.write_schemas import ParametreSecuriteUpdate
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/securite", tags=["securite"])


@router.get("/audit", response_model=JournalAuditPage)
def journal_audit(
    boutique_id: str | None = None,
    utilisateur_id: str | None = None,
    client_id: str | None = None,
    canal: str | None = None,
    methode: str | None = None,
    q: str | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    page: int = 1,
    taille: int = 50,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> JournalAuditPage:
    # Accès en lecture aux journaux d'audit réservé à l'administrateur (cf. CDC §7.3).
    require_permission(db, current_user, SECURITE_GESTION)
    taille = max(1, min(taille, 200))
    page = max(1, page)

    query = db.query(JournalAuditDB)
    if boutique_id:
        query = query.filter(JournalAuditDB.boutique_id == boutique_id)
    if utilisateur_id:
        query = query.filter(JournalAuditDB.utilisateur_id == utilisateur_id)
    if client_id:
        query = query.filter(JournalAuditDB.client_id == client_id)
    if canal:
        query = query.filter(JournalAuditDB.canal == canal)
    if methode:
        query = query.filter(JournalAuditDB.methode == methode)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(JournalAuditDB.action.ilike(like), JournalAuditDB.auteur.ilike(like), JournalAuditDB.chemin.ilike(like)))
    if date_debut:
        query = query.filter(JournalAuditDB.horodatage >= date_debut)
    if date_fin:
        query = query.filter(JournalAuditDB.horodatage <= date_fin)

    total = query.count()
    items = (
        query.order_by(JournalAuditDB.horodatage.desc())
        .offset((page - 1) * taille)
        .limit(taille)
        .all()
    )
    return JournalAuditPage(items=items, total=total)


@router.get("/parametres", response_model=list[ParametreSecurite])
def parametres_securite(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[ParametreSecuriteDB]:
    require_permission(db, current_user, SECURITE_GESTION)
    return sorted(db.query(ParametreSecuriteDB).all(), key=lambda p: p.ordre)


@router.put("/parametres/{parametre_id}", response_model=ParametreSecurite)
def modifier_parametre_securite(
    parametre_id: str,
    payload: ParametreSecuriteUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ParametreSecuriteDB:
    require_permission(db, current_user, SECURITE_GESTION)
    p = db.get(ParametreSecuriteDB, parametre_id)
    if not p:
        raise HTTPException(status_code=404, detail="Paramètre introuvable")
    p.actif = payload.actif
    p.updated_by = f"{current_user.prenom} {current_user.nom}"
    log_audit(
        db,
        f"Paramètre de sécurité { 'activé' if payload.actif else 'désactivé' } — {p.label}",
        f"{current_user.prenom} {current_user.nom}",
    )
    db.commit()
    db.refresh(p)
    return p
