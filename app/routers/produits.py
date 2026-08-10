import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import ProduitDB
from app.models.schemas import Produit, Secteur
from app.models.write_schemas import ProduitCreate, ProduitUpdate

router = APIRouter(prefix="/api/v1/produits", tags=["produits"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "produits"
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


@router.get("", response_model=list[Produit])
def list_produits(q: str | None = None, secteur: Secteur | None = None, db: Session = Depends(get_db)) -> list[ProduitDB]:
    query = db.query(ProduitDB)
    if secteur:
        query = query.filter(ProduitDB.secteur == secteur)
    if q:
        query = query.filter(ProduitDB.nom.ilike(f"%{q}%"))
    return query.all()


@router.get("/{produit_id}", response_model=Produit)
def get_produit(produit_id: str, db: Session = Depends(get_db)) -> ProduitDB:
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    return p


@router.post("", response_model=Produit, status_code=201)
def create_produit(
    payload: ProduitCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProduitDB:
    if db.query(ProduitDB).filter(ProduitDB.code_barres == payload.code_barres).first():
        raise HTTPException(status_code=409, detail="Un produit avec ce code-barres existe déjà")
    p = ProduitDB(id=str(uuid.uuid4())[:8], **payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.put("/{produit_id}", response_model=Produit)
def update_produit(
    produit_id: str,
    payload: ProduitUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProduitDB:
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{produit_id}", status_code=204)
def delete_produit(
    produit_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> None:
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    if p.image_url:
        _delete_image_file(p.image_url)
    db.delete(p)
    db.commit()


@router.post("/{produit_id}/image", response_model=Produit)
def upload_image(
    produit_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProduitDB:
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    ext = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Format d'image non supporté (jpeg, png, webp uniquement)")

    if p.image_url:
        _delete_image_file(p.image_url)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{produit_id}-{uuid.uuid4().hex[:8]}{ext}"
    with open(UPLOADS_DIR / filename, "wb") as f:
        f.write(file.file.read())

    p.image_url = f"/uploads/produits/{filename}"
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{produit_id}/image", response_model=Produit)
def delete_image(
    produit_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ProduitDB:
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    if p.image_url:
        _delete_image_file(p.image_url)
        p.image_url = None
        db.commit()
        db.refresh(p)
    return p


def _delete_image_file(image_url: str) -> None:
    filename = image_url.rsplit("/", 1)[-1]
    path = UPLOADS_DIR / filename
    if path.exists():
        path.unlink()
