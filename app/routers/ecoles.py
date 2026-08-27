import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import ECOLE_GESTION
from app.core.security import get_current_user
from app.db_models.models import EcoleDB, UtilisateurDB
from app.models.schemas import Ecole
from app.models.write_schemas import EcoleCreate, EcoleUpdate
from app.core.db_errors import commit_or_409

router = APIRouter(prefix="/api/v1/ecoles", tags=["ecoles"])


@router.get("", response_model=list[Ecole])
def list_ecoles(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[EcoleDB]:
    # Lecture ouverte à tout utilisateur authentifié — la fiche enseignant et le tableau de
    # bord ont besoin de résoudre le nom de l'école sans nécessairement gérer les écoles.
    return db.query(EcoleDB).all()


@router.post("", response_model=Ecole, status_code=201)
def create_ecole(
    payload: EcoleCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> EcoleDB:
    require_permission(db, current_user, ECOLE_GESTION)
    auteur = f"{current_user.prenom} {current_user.nom}"
    e = EcoleDB(id=str(uuid.uuid4())[:8], created_by=auteur, updated_by=auteur, **payload.model_dump())
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@router.put("/{ecole_id}", response_model=Ecole)
def update_ecole(
    ecole_id: str,
    payload: EcoleUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> EcoleDB:
    require_permission(db, current_user, ECOLE_GESTION)
    e = db.get(EcoleDB, ecole_id)
    if not e:
        raise HTTPException(status_code=404, detail="École introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(e, field, value)
    e.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(e)
    return e


@router.delete("/{ecole_id}", status_code=204)
def delete_ecole(
    ecole_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, ECOLE_GESTION)
    e = db.get(EcoleDB, ecole_id)
    if not e:
        raise HTTPException(status_code=404, detail="École introuvable")
    db.delete(e)
    commit_or_409(db, "Impossible de supprimer cette école : des enseignants ou des barèmes y sont encore rattachés.")
