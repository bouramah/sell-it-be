from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import UTILISATEURS_GESTION
from app.core.security import get_current_user
from app.db_models.models import BoutiqueDB, UtilisateurDB
from app.services.push import envoyer_notification_push

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class NotificationPushInput(BaseModel):
    cible: Literal["utilisateur", "boutique"]
    utilisateur_id: str | None = None
    boutique_id: str | None = None
    titre: str
    message: str


class NotificationPushResult(BaseModel):
    destinataires: int
    notifies: int


@router.post("/push", response_model=NotificationPushResult)
def envoyer_push(
    payload: NotificationPushInput,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> NotificationPushResult:
    """Envoi manuel d'une notification push, depuis l'écran d'administration, à un
    utilisateur précis ou à tout le personnel actif d'une boutique — cf. CDC §6.1
    "notification multicanal". Compte séparément les destinataires trouvés et ceux
    réellement notifiés (un compte sans token push enregistré ne reçoit rien)."""
    require_permission(db, current_user, UTILISATEURS_GESTION)

    if payload.cible == "utilisateur":
        if not payload.utilisateur_id:
            raise HTTPException(status_code=400, detail="utilisateur_id requis pour une cible 'utilisateur'")
        u = db.get(UtilisateurDB, payload.utilisateur_id)
        if not u:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable")
        destinataires = [u]
    else:
        if not payload.boutique_id:
            raise HTTPException(status_code=400, detail="boutique_id requis pour une cible 'boutique'")
        boutique = db.get(BoutiqueDB, payload.boutique_id)
        if not boutique:
            raise HTTPException(status_code=404, detail="Boutique introuvable")
        destinataires = (
            db.query(UtilisateurDB)
            .join(UtilisateurDB.boutiques)
            .filter(BoutiqueDB.id == payload.boutique_id, UtilisateurDB.statut == "actif")
            .all()
        )

    notifies = 0
    for u in destinataires:
        if u.push_token and envoyer_notification_push(u.push_token, payload.titre, payload.message):
            notifies += 1

    return NotificationPushResult(destinataires=len(destinataires), notifies=notifies)
