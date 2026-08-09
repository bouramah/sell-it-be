import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_user
from app.data.fixtures import FOURNISSEURS
from app.db_models.models import BoutiqueDB, BoutiqueSecteurDB
from app.models.schemas import Boutique, Fournisseur, Secteur, StatutBoutique
from app.models.write_schemas import BoutiqueCreate, BoutiqueUpdate

router = APIRouter(prefix="/api/v1", tags=["reseau"])


def _to_schema(b: BoutiqueDB) -> Boutique:
    return Boutique(
        id=b.id,
        nom=b.nom,
        secteurs=[s.secteur for s in b.secteurs],
        quartier=b.quartier,
        commune=b.commune,
        ville=b.ville,
        horaires=b.horaires,
        responsable=b.responsable,
        statut=b.statut,
        telephone=b.telephone,
    )


@router.get("/boutiques", response_model=list[Boutique])
def list_boutiques(
    ville: str | None = None,
    secteur: Secteur | None = None,
    statut: StatutBoutique | None = None,
    db: Session = Depends(get_db),
) -> list[Boutique]:
    query = db.query(BoutiqueDB)
    if ville:
        query = query.filter(BoutiqueDB.ville == ville)
    if statut:
        query = query.filter(BoutiqueDB.statut == statut)
    result = [_to_schema(b) for b in query.all()]
    if secteur:
        result = [b for b in result if secteur in b.secteurs]
    return result


@router.get("/boutiques/{boutique_id}", response_model=Boutique)
def get_boutique(boutique_id: str, db: Session = Depends(get_db)) -> Boutique:
    b = db.get(BoutiqueDB, boutique_id)
    if not b:
        raise HTTPException(status_code=404, detail="Boutique introuvable")
    return _to_schema(b)


@router.post("/boutiques", response_model=Boutique, status_code=201)
def create_boutique(
    payload: BoutiqueCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Boutique:
    boutique_id = str(uuid.uuid4())[:8]
    b = BoutiqueDB(
        id=boutique_id,
        nom=payload.nom,
        quartier=payload.quartier,
        commune=payload.commune,
        ville=payload.ville,
        horaires=payload.horaires,
        responsable=payload.responsable,
        statut=payload.statut,
        telephone=payload.telephone,
    )
    b.secteurs = [BoutiqueSecteurDB(boutique_id=boutique_id, secteur=s) for s in payload.secteurs]
    db.add(b)
    db.commit()
    db.refresh(b)
    return _to_schema(b)


@router.put("/boutiques/{boutique_id}", response_model=Boutique)
def update_boutique(
    boutique_id: str,
    payload: BoutiqueUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Boutique:
    b = db.get(BoutiqueDB, boutique_id)
    if not b:
        raise HTTPException(status_code=404, detail="Boutique introuvable")

    data = payload.model_dump(exclude_unset=True, exclude={"secteurs"})
    for field, value in data.items():
        setattr(b, field, value)

    if payload.secteurs is not None:
        b.secteurs = [BoutiqueSecteurDB(boutique_id=boutique_id, secteur=s) for s in payload.secteurs]

    db.commit()
    db.refresh(b)
    return _to_schema(b)


@router.delete("/boutiques/{boutique_id}", status_code=204)
def delete_boutique(
    boutique_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    b = db.get(BoutiqueDB, boutique_id)
    if not b:
        raise HTTPException(status_code=404, detail="Boutique introuvable")
    db.delete(b)
    db.commit()


@router.get("/fournisseurs", response_model=list[Fournisseur])
def list_fournisseurs(secteur: Secteur | None = None) -> list[Fournisseur]:
    if secteur:
        return [f for f in FOURNISSEURS if f.secteur == secteur]
    return FOURNISSEURS
