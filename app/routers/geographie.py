import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.db_errors import commit_or_409
from app.core.module_actions import REFERENTIELS_GESTION
from app.core.security import get_current_user
from app.db_models.models import CommuneDB, QuartierGeoDB, RegionDB, SecteurGeoDB, UtilisateurDB, VilleDB
from app.models.schemas import Commune, QuartierGeo, Region, SecteurGeo, Ville
from app.models.write_schemas import CommuneInput, QuartierGeoInput, RegionInput, SecteurGeoInput, VilleInput

router = APIRouter(prefix="/api/v1", tags=["geographie"])

# Découpage administratif Région > Ville > Commune > Quartier > Secteur — sert à localiser
# précisément les clients (tournées de livraison, future appli mobile client). CRUD simple,
# cascade delete côté DB (supprimer une région supprime ses villes, etc.), gatée par la même
# permission que les autres référentiels gérés.


@router.get("/regions", response_model=list[Region])
def list_regions(db: Session = Depends(get_db)) -> list[RegionDB]:
    return db.query(RegionDB).order_by(RegionDB.nom).all()


@router.post("/regions", response_model=Region, status_code=201)
def creer_region(payload: RegionInput, db: Session = Depends(get_db), current_user: UtilisateurDB = Depends(get_current_user)) -> RegionDB:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    auteur = f"{current_user.prenom} {current_user.nom}"
    r = RegionDB(id=str(uuid.uuid4())[:8], nom=payload.nom, created_by=auteur, updated_by=auteur)
    db.add(r)
    commit_or_409(db, "Une région avec ce nom existe déjà")
    db.refresh(r)
    return r


@router.delete("/regions/{region_id}", status_code=204)
def supprimer_region(region_id: str, db: Session = Depends(get_db), current_user: UtilisateurDB = Depends(get_current_user)) -> None:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    r = db.get(RegionDB, region_id)
    if not r:
        raise HTTPException(status_code=404, detail="Région introuvable")
    db.delete(r)
    db.commit()


@router.get("/villes", response_model=list[Ville])
def list_villes(region_id: str | None = None, db: Session = Depends(get_db)) -> list[VilleDB]:
    query = db.query(VilleDB)
    if region_id:
        query = query.filter(VilleDB.region_id == region_id)
    return query.order_by(VilleDB.nom).all()


@router.post("/villes", response_model=Ville, status_code=201)
def creer_ville(payload: VilleInput, db: Session = Depends(get_db), current_user: UtilisateurDB = Depends(get_current_user)) -> VilleDB:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    if not db.get(RegionDB, payload.region_id):
        raise HTTPException(status_code=404, detail="Région introuvable")
    auteur = f"{current_user.prenom} {current_user.nom}"
    v = VilleDB(id=str(uuid.uuid4())[:8], nom=payload.nom, region_id=payload.region_id, created_by=auteur, updated_by=auteur)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.delete("/villes/{ville_id}", status_code=204)
def supprimer_ville(ville_id: str, db: Session = Depends(get_db), current_user: UtilisateurDB = Depends(get_current_user)) -> None:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    v = db.get(VilleDB, ville_id)
    if not v:
        raise HTTPException(status_code=404, detail="Ville introuvable")
    db.delete(v)
    db.commit()


@router.get("/communes", response_model=list[Commune])
def list_communes(ville_id: str | None = None, db: Session = Depends(get_db)) -> list[CommuneDB]:
    query = db.query(CommuneDB)
    if ville_id:
        query = query.filter(CommuneDB.ville_id == ville_id)
    return query.order_by(CommuneDB.nom).all()


@router.post("/communes", response_model=Commune, status_code=201)
def creer_commune(payload: CommuneInput, db: Session = Depends(get_db), current_user: UtilisateurDB = Depends(get_current_user)) -> CommuneDB:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    if not db.get(VilleDB, payload.ville_id):
        raise HTTPException(status_code=404, detail="Ville introuvable")
    auteur = f"{current_user.prenom} {current_user.nom}"
    c = CommuneDB(id=str(uuid.uuid4())[:8], nom=payload.nom, ville_id=payload.ville_id, created_by=auteur, updated_by=auteur)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/communes/{commune_id}", status_code=204)
def supprimer_commune(commune_id: str, db: Session = Depends(get_db), current_user: UtilisateurDB = Depends(get_current_user)) -> None:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    c = db.get(CommuneDB, commune_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commune introuvable")
    db.delete(c)
    db.commit()


@router.get("/quartiers-geo", response_model=list[QuartierGeo])
def list_quartiers_geo(commune_id: str | None = None, db: Session = Depends(get_db)) -> list[QuartierGeoDB]:
    query = db.query(QuartierGeoDB)
    if commune_id:
        query = query.filter(QuartierGeoDB.commune_id == commune_id)
    return query.order_by(QuartierGeoDB.nom).all()


@router.post("/quartiers-geo", response_model=QuartierGeo, status_code=201)
def creer_quartier_geo(payload: QuartierGeoInput, db: Session = Depends(get_db), current_user: UtilisateurDB = Depends(get_current_user)) -> QuartierGeoDB:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    if not db.get(CommuneDB, payload.commune_id):
        raise HTTPException(status_code=404, detail="Commune introuvable")
    auteur = f"{current_user.prenom} {current_user.nom}"
    q = QuartierGeoDB(id=str(uuid.uuid4())[:8], nom=payload.nom, commune_id=payload.commune_id, created_by=auteur, updated_by=auteur)
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


@router.delete("/quartiers-geo/{quartier_id}", status_code=204)
def supprimer_quartier_geo(quartier_id: str, db: Session = Depends(get_db), current_user: UtilisateurDB = Depends(get_current_user)) -> None:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    q = db.get(QuartierGeoDB, quartier_id)
    if not q:
        raise HTTPException(status_code=404, detail="Quartier introuvable")
    db.delete(q)
    db.commit()


@router.get("/secteurs-geo", response_model=list[SecteurGeo])
def list_secteurs_geo(quartier_id: str | None = None, db: Session = Depends(get_db)) -> list[SecteurGeoDB]:
    query = db.query(SecteurGeoDB)
    if quartier_id:
        query = query.filter(SecteurGeoDB.quartier_id == quartier_id)
    return query.order_by(SecteurGeoDB.nom).all()


@router.post("/secteurs-geo", response_model=SecteurGeo, status_code=201)
def creer_secteur_geo(payload: SecteurGeoInput, db: Session = Depends(get_db), current_user: UtilisateurDB = Depends(get_current_user)) -> SecteurGeoDB:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    if not db.get(QuartierGeoDB, payload.quartier_id):
        raise HTTPException(status_code=404, detail="Quartier introuvable")
    auteur = f"{current_user.prenom} {current_user.nom}"
    s = SecteurGeoDB(id=str(uuid.uuid4())[:8], nom=payload.nom, quartier_id=payload.quartier_id, created_by=auteur, updated_by=auteur)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/secteurs-geo/{secteur_id}", status_code=204)
def supprimer_secteur_geo(secteur_id: str, db: Session = Depends(get_db), current_user: UtilisateurDB = Depends(get_current_user)) -> None:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    s = db.get(SecteurGeoDB, secteur_id)
    if not s:
        raise HTTPException(status_code=404, detail="Secteur introuvable")
    db.delete(s)
    db.commit()
