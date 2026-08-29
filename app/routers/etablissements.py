import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import ETABLISSEMENT_GESTION
from app.core.security import get_current_user
from app.db_models.models import EtablissementDB, UtilisateurDB
from app.models.schemas import Etablissement
from app.models.write_schemas import EtablissementCreate, EtablissementUpdate
from app.core.db_errors import commit_or_409

router = APIRouter(prefix="/api/v1/etablissements", tags=["etablissements"])


@router.get("", response_model=list[Etablissement])
def list_etablissements(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[EtablissementDB]:
    # Lecture ouverte à tout utilisateur authentifié — la fiche bénéficiaire et le tableau de
    # bord ont besoin de résoudre le nom de l'établissement sans nécessairement le gérer.
    return db.query(EtablissementDB).all()


@router.post("", response_model=Etablissement, status_code=201)
def create_etablissement(
    payload: EtablissementCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> EtablissementDB:
    require_permission(db, current_user, ETABLISSEMENT_GESTION)
    auteur = f"{current_user.prenom} {current_user.nom}"
    e = EtablissementDB(id=str(uuid.uuid4())[:8], created_by=auteur, updated_by=auteur, **payload.model_dump())
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


@router.put("/{etablissement_id}", response_model=Etablissement)
def update_etablissement(
    etablissement_id: str,
    payload: EtablissementUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> EtablissementDB:
    require_permission(db, current_user, ETABLISSEMENT_GESTION)
    e = db.get(EtablissementDB, etablissement_id)
    if not e:
        raise HTTPException(status_code=404, detail="Établissement introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(e, field, value)
    e.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(e)
    return e


@router.delete("/{etablissement_id}", status_code=204)
def delete_etablissement(
    etablissement_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, ETABLISSEMENT_GESTION)
    e = db.get(EtablissementDB, etablissement_id)
    if not e:
        raise HTTPException(status_code=404, detail="Établissement introuvable")
    db.delete(e)
    commit_or_409(db, "Impossible de supprimer cet établissement : des bénéficiaires ou des barèmes y sont encore rattachés.")
