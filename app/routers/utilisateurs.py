import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_user, hash_password
from app.data.fixtures import PERMISSIONS
from app.db_models.models import BoutiqueDB, UtilisateurDB
from app.models.schemas import Role, Utilisateur
from app.models.write_schemas import UtilisateurCreate, UtilisateurUpdate

router = APIRouter(prefix="/api/v1", tags=["utilisateurs"])


def _to_schema(u: UtilisateurDB) -> Utilisateur:
    return Utilisateur(
        id=u.id,
        nom=u.nom,
        prenom=u.prenom,
        contact=u.contact,
        role=u.role,
        boutique_ids=[b.id for b in u.boutiques],
        statut=u.statut,
        derniere_connexion=u.derniere_connexion,
    )


@router.get("/utilisateurs", response_model=list[Utilisateur])
def list_utilisateurs(role: Role | None = None, boutique_id: str | None = None, db: Session = Depends(get_db)) -> list[Utilisateur]:
    query = db.query(UtilisateurDB)
    if role:
        query = query.filter(UtilisateurDB.role == role)
    result = [_to_schema(u) for u in query.all()]
    if boutique_id:
        result = [u for u in result if boutique_id in u.boutique_ids]
    return result


@router.post("/utilisateurs", response_model=Utilisateur, status_code=201)
def create_utilisateur(
    payload: UtilisateurCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Utilisateur:
    if db.query(UtilisateurDB).filter(UtilisateurDB.contact == payload.contact).first():
        raise HTTPException(status_code=409, detail="Un utilisateur avec ce contact existe déjà")

    boutiques = db.query(BoutiqueDB).filter(BoutiqueDB.id.in_(payload.boutique_ids)).all()
    u = UtilisateurDB(
        id=str(uuid.uuid4())[:8],
        nom=payload.nom,
        prenom=payload.prenom,
        contact=payload.contact,
        mot_de_passe_hash=hash_password(payload.mot_de_passe),
        role=payload.role,
        statut=payload.statut,
        boutiques=boutiques,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return _to_schema(u)


@router.put("/utilisateurs/{utilisateur_id}", response_model=Utilisateur)
def update_utilisateur(
    utilisateur_id: str,
    payload: UtilisateurUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Utilisateur:
    u = db.get(UtilisateurDB, utilisateur_id)
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    data = payload.model_dump(exclude_unset=True, exclude={"mot_de_passe", "boutique_ids"})
    for field, value in data.items():
        setattr(u, field, value)

    if payload.mot_de_passe:
        u.mot_de_passe_hash = hash_password(payload.mot_de_passe)
    if payload.boutique_ids is not None:
        u.boutiques = db.query(BoutiqueDB).filter(BoutiqueDB.id.in_(payload.boutique_ids)).all()

    db.commit()
    db.refresh(u)
    return _to_schema(u)


@router.delete("/utilisateurs/{utilisateur_id}", status_code=204)
def delete_utilisateur(
    utilisateur_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    u = db.get(UtilisateurDB, utilisateur_id)
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    db.delete(u)
    db.commit()


@router.get("/permissions")
def get_permissions() -> list[dict]:
    return PERMISSIONS
