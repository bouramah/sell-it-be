import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db_models.models import JournalAuditDB


def log_audit(db: Session, action: str, auteur: str, boutique_id: str | None = None) -> None:
    db.add(JournalAuditDB(
        id=str(uuid.uuid4())[:8],
        horodatage=datetime.now(timezone.utc),
        action=action,
        auteur=auteur,
        boutique_id=boutique_id,
    ))
