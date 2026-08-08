from fastapi import APIRouter

from app.data.fixtures import PERMISSIONS, UTILISATEURS
from app.models.schemas import Role, Utilisateur

router = APIRouter(prefix="/api/v1", tags=["utilisateurs"])


@router.get("/utilisateurs", response_model=list[Utilisateur])
def list_utilisateurs(role: Role | None = None, boutique_id: str | None = None) -> list[Utilisateur]:
    result = UTILISATEURS
    if role:
        result = [u for u in result if u.role == role]
    if boutique_id:
        result = [u for u in result if boutique_id in u.boutique_ids]
    return result


@router.get("/permissions")
def get_permissions() -> list[dict]:
    return PERMISSIONS
