import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import REFERENTIELS_GESTION
from app.core.security import get_current_user
from app.data.fixtures import REFERENTIELS
from app.db_models.models import ReferentielDB, UtilisateurDB
from app.models.schemas import ReferentielItem
from app.models.write_schemas import ReferentielCreate, ReferentielUpdate

router = APIRouter(prefix="/api/v1/parametres", tags=["parametres"])


def _managed_categories(db: Session) -> list[str]:
    rows = db.query(ReferentielDB.categorie).distinct().all()
    categories = {r[0] for r in rows}
    categories.update(REFERENTIELS.keys())
    return sorted(categories)


@router.get("/referentiels", response_model=dict[str, list[ReferentielItem]])
def list_referentiels(db: Session = Depends(get_db)) -> dict[str, list[ReferentielItem]]:
    result: dict[str, list[ReferentielItem]] = {}
    for categorie in _managed_categories(db):
        rows = db.query(ReferentielDB).filter(ReferentielDB.categorie == categorie).all()
        result[categorie] = [ReferentielItem(id=r.id, nom=r.nom) for r in rows]
    return result


@router.get("/referentiels/{categorie}", response_model=list[ReferentielItem])
def get_referentiel(categorie: str, db: Session = Depends(get_db)) -> list[ReferentielItem]:
    rows = db.query(ReferentielDB).filter(ReferentielDB.categorie == categorie).all()
    return [ReferentielItem(id=r.id, nom=r.nom) for r in rows]


@router.post("/referentiels/{categorie}", response_model=ReferentielItem, status_code=201)
def create_referentiel_item(
    categorie: str,
    payload: ReferentielCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ReferentielItem:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    auteur = f"{current_user.prenom} {current_user.nom}"
    item = ReferentielDB(id=str(uuid.uuid4())[:8], categorie=categorie, nom=payload.nom, created_by=auteur, updated_by=auteur)
    db.add(item)
    db.commit()
    db.refresh(item)
    return ReferentielItem(id=item.id, nom=item.nom)


@router.put("/referentiels/{categorie}/{item_id}", response_model=ReferentielItem)
def update_referentiel_item(
    categorie: str,
    item_id: str,
    payload: ReferentielUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ReferentielItem:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    item = db.query(ReferentielDB).filter(ReferentielDB.id == item_id, ReferentielDB.categorie == categorie).first()
    if not item:
        raise HTTPException(status_code=404, detail="Référentiel introuvable")
    item.nom = payload.nom
    item.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(item)
    return ReferentielItem(id=item.id, nom=item.nom)


@router.delete("/referentiels/{categorie}/{item_id}", status_code=204)
def delete_referentiel_item(
    categorie: str,
    item_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    item = db.query(ReferentielDB).filter(ReferentielDB.id == item_id, ReferentielDB.categorie == categorie).first()
    if not item:
        raise HTTPException(status_code=404, detail="Référentiel introuvable")
    db.delete(item)
    db.commit()
