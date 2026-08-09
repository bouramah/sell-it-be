from fastapi import APIRouter

from app.data.fixtures import JOURNAL_AUDIT, PARAMETRES_SECURITE
from app.models.schemas import JournalAuditEntry, ParametreSecurite

router = APIRouter(prefix="/api/v1/securite", tags=["securite"])


@router.get("/audit", response_model=list[JournalAuditEntry])
def journal_audit(boutique_id: str | None = None) -> list[JournalAuditEntry]:
    rows = JOURNAL_AUDIT
    if boutique_id:
        rows = [a for a in rows if a.boutique_id == boutique_id]
    return sorted(rows, key=lambda a: a.horodatage, reverse=True)


@router.get("/parametres", response_model=list[ParametreSecurite])
def parametres_securite() -> list[ParametreSecurite]:
    return PARAMETRES_SECURITE
