import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db_models.models import JournalAuditDB


def log_audit(
    db: Session,
    action: str,
    auteur: str,
    boutique_id: str | None = None,
    valeur_avant: dict[str, Any] | None = None,
    valeur_apres: dict[str, Any] | None = None,
) -> None:
    db.add(JournalAuditDB(
        id=str(uuid.uuid4())[:8],
        horodatage=datetime.now(timezone.utc),
        action=action,
        auteur=auteur,
        boutique_id=boutique_id,
        valeur_avant=json.dumps(valeur_avant, default=str, ensure_ascii=False) if valeur_avant is not None else None,
        valeur_apres=json.dumps(valeur_apres, default=str, ensure_ascii=False) if valeur_apres is not None else None,
    ))
