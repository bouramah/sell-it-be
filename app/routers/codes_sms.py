"""Secours SMS — visible uniquement de l'administrateur (siège) : le fournisseur SMS a parfois
des échecs d'envoi, cet endpoint permet de retrouver un code/mot de passe en clair pour le
communiquer par un autre canal quand l'utilisateur ne l'a jamais reçu (cf.
app/core/module_actions.py::SECOURS_SMS_GESTION)."""
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import SECOURS_SMS_GESTION
from app.core.security import get_current_user
from app.db_models.models import OtpCodeDB, UtilisateurDB

router = APIRouter(prefix="/api/v1/codes-sms", tags=["codes-sms"])

OBJECTIF_LABELS = {
    "connexion": "2FA connexion (staff)",
    "reinitialisation": "Mot de passe oublié (staff)",
    "connexion_client": "Connexion client (mobile)",
    "mot_de_passe_admin": "Mot de passe généré par un administrateur",
}

DUREE_HISTORIQUE = timedelta(days=7)
LIMITE_LIGNES = 200


class CodeSms(BaseModel):
    id: str
    contact: str
    code_clair: str | None
    objectif: str
    objectif_libelle: str
    created_at: datetime
    expires_at: datetime
    statut: str  # actif | utilise | expire


@router.get("", response_model=list[CodeSms])
def list_codes_sms(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[CodeSms]:
    require_permission(db, current_user, SECOURS_SMS_GESTION)
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now_naive - DUREE_HISTORIQUE
    rows = (
        db.query(OtpCodeDB)
        .filter(OtpCodeDB.created_at > cutoff)
        .order_by(OtpCodeDB.created_at.desc())
        .limit(LIMITE_LIGNES)
        .all()
    )
    resultat = []
    for r in rows:
        if r.used:
            statut = "utilise"
        elif r.expires_at < now_naive:
            statut = "expire"
        else:
            statut = "actif"
        resultat.append(CodeSms(
            id=r.id, contact=r.contact, code_clair=r.code_clair, objectif=r.objectif,
            objectif_libelle=OBJECTIF_LABELS.get(r.objectif, r.objectif),
            created_at=r.created_at, expires_at=r.expires_at, statut=statut,
        ))
    return resultat
