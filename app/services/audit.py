import contextvars
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db_models.models import JournalAuditDB

class AuditFlag:
    """Objet mutable partagé (et non une simple valeur réassignée) : FastAPI exécute les
    endpoints `def` synchrones dans un thread de threadpool (anyio.to_thread.run_sync), qui
    hérite d'une COPIE du contexte — un `ContextVar.set()` fait depuis ce thread ne serait
    jamais visible dans le thread appelant une fois l'endpoint terminé. Muter un attribut d'un
    objet déjà référencé par les deux côtés fonctionne, car ce n'est pas la contextvar elle-même
    qui change, seulement l'objet qu'elle pointe déjà — donc aucune copie de contexte ne l'isole."""

    __slots__ = ("logged",)

    def __init__(self) -> None:
        self.logged = False


# Le middleware de traçage automatique (app/core/audit_middleware.py) positionne cette contextvar
# sur un AuditFlag frais AVANT d'appeler l'endpoint, puis vérifie flag.logged après coup pour ne
# pas ajouter une deuxième ligne générique quand le handler a déjà appelé log_audit() lui-même
# avec un libellé métier riche (avant/après inclus). Portée par requête (pas de fuite entre
# requêtes concurrentes : chaque requête reçoit son propre AuditFlag).
current_audit_flag: contextvars.ContextVar["AuditFlag | None"] = contextvars.ContextVar("current_audit_flag", default=None)


def log_audit(
    db: Session,
    action: str,
    auteur: str,
    boutique_id: str | None = None,
    valeur_avant: dict[str, Any] | None = None,
    valeur_apres: dict[str, Any] | None = None,
    utilisateur_id: str | None = None,
    client_id: str | None = None,
) -> None:
    flag = current_audit_flag.get()
    if flag is not None:
        flag.logged = True
    db.add(JournalAuditDB(
        id=str(uuid.uuid4())[:8],
        horodatage=datetime.now(timezone.utc),
        action=action,
        auteur=auteur,
        boutique_id=boutique_id,
        valeur_avant=json.dumps(valeur_avant, default=str, ensure_ascii=False) if valeur_avant is not None else None,
        valeur_apres=json.dumps(valeur_apres, default=str, ensure_ascii=False) if valeur_apres is not None else None,
        utilisateur_id=utilisateur_id,
        client_id=client_id,
    ))
