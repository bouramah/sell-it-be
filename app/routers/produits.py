import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.core.authorization import require_role
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import ProduitDB, ProduitImageDB, UtilisateurDB
from app.models.schemas import Produit, ProduitImage, Role
from app.models.write_schemas import ProduitCreate, ProduitUpdate

router = APIRouter(prefix="/api/v1/produits", tags=["produits"])

ROLES_GESTION_PRODUITS = (Role.gerant, Role.responsable_achats, Role.administrateur)

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "produits"
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _to_schema(p: ProduitDB) -> Produit:
    return Produit(
        id=p.id, nom=p.nom, secteur=p.secteur, categorie=p.categorie, prix=p.prix, unite=p.unite,
        code_barres=p.code_barres, date_peremption=p.date_peremption,
        images=[ProduitImage(id=img.id, url=img.url, position=img.position) for img in p.images],
    )


def _delete_image_file(url: str) -> None:
    filename = url.rsplit("/", 1)[-1]
    path = UPLOADS_DIR / filename
    if path.exists():
        path.unlink()


@router.get("", response_model=list[Produit])
def list_produits(q: str | None = None, secteur: str | None = None, db: Session = Depends(get_db)) -> list[Produit]:
    query = db.query(ProduitDB)
    if secteur:
        query = query.filter(ProduitDB.secteur == secteur)
    if q:
        query = query.filter(ProduitDB.nom.ilike(f"%{q}%"))
    return [_to_schema(p) for p in query.all()]


@router.get("/{produit_id}", response_model=Produit)
def get_produit(produit_id: str, db: Session = Depends(get_db)) -> Produit:
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    return _to_schema(p)


@router.post("", response_model=Produit, status_code=201)
def create_produit(
    payload: ProduitCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Produit:
    require_role(current_user, *ROLES_GESTION_PRODUITS)
    if db.query(ProduitDB).filter(ProduitDB.code_barres == payload.code_barres).first():
        raise HTTPException(status_code=409, detail="Un produit avec ce code-barres existe déjà")
    p = ProduitDB(id=str(uuid.uuid4())[:8], **payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_schema(p)


@router.put("/{produit_id}", response_model=Produit)
def update_produit(
    produit_id: str,
    payload: ProduitUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Produit:
    require_role(current_user, *ROLES_GESTION_PRODUITS)
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return _to_schema(p)


@router.delete("/{produit_id}", status_code=204)
def delete_produit(
    produit_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_role(current_user, *ROLES_GESTION_PRODUITS)
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    for img in p.images:
        _delete_image_file(img.url)
    db.delete(p)
    db.commit()


@router.post("/{produit_id}/images", response_model=Produit)
def uploader_image(
    produit_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Produit:
    require_role(current_user, *ROLES_GESTION_PRODUITS)
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    ext = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Format d'image non supporté (jpeg, png, webp uniquement)")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{produit_id}-{uuid.uuid4().hex[:8]}{ext}"
    with open(UPLOADS_DIR / filename, "wb") as f:
        f.write(file.file.read())

    next_position = max((img.position for img in p.images), default=-1) + 1
    db.add(ProduitImageDB(id=str(uuid.uuid4())[:8], produit_id=produit_id, url=f"/uploads/produits/{filename}", position=next_position))
    db.commit()
    db.refresh(p)
    return _to_schema(p)


@router.delete("/{produit_id}/images/{image_id}", response_model=Produit)
def supprimer_image(
    produit_id: str,
    image_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Produit:
    require_role(current_user, *ROLES_GESTION_PRODUITS)
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    img = db.get(ProduitImageDB, image_id)
    if img and img.produit_id == produit_id:
        _delete_image_file(img.url)
        db.delete(img)
        db.commit()
        db.refresh(p)
    return _to_schema(p)
