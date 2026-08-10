import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import CommandeClientDB, LivraisonDB
from app.models.schemas import Livraison, StatutCommandeClient, StatutLivraison
from app.models.write_schemas import LivraisonCreate, LivraisonStatutUpdate

router = APIRouter(prefix="/api/v1/livraisons", tags=["livraisons"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "livraisons"
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _delete_preuve_file(url: str) -> None:
    filename = url.rsplit("/", 1)[-1]
    path = UPLOADS_DIR / filename
    if path.exists():
        path.unlink()


@router.get("", response_model=list[Livraison])
def list_livraisons(boutique_id: str | None = None, db: Session = Depends(get_db)) -> list[LivraisonDB]:
    query = db.query(LivraisonDB)
    if boutique_id:
        query = query.filter(LivraisonDB.boutique_id == boutique_id)
    return query.all()


@router.post("", response_model=Livraison, status_code=201)
def create_livraison(
    payload: LivraisonCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> LivraisonDB:
    commande = db.get(CommandeClientDB, payload.commande_id)
    if not commande:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    l = LivraisonDB(
        id=str(uuid.uuid4())[:8], commande_id=payload.commande_id, livreur=payload.livreur,
        boutique_id=payload.boutique_id, adresse=payload.adresse, creneau=payload.creneau,
        statut=StatutLivraison.preparee,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


@router.put("/{livraison_id}/statut", response_model=Livraison)
def update_statut(
    livraison_id: str,
    payload: LivraisonStatutUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> LivraisonDB:
    l = db.get(LivraisonDB, livraison_id)
    if not l:
        raise HTTPException(status_code=404, detail="Livraison introuvable")
    l.statut = payload.statut
    if payload.statut == StatutLivraison.livree:
        commande = db.get(CommandeClientDB, l.commande_id)
        if commande and commande.statut != StatutCommandeClient.annulee:
            commande.statut = StatutCommandeClient.livree
    db.commit()
    db.refresh(l)
    return l


@router.post("/{livraison_id}/preuve", response_model=Livraison)
def uploader_preuve(
    livraison_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> LivraisonDB:
    l = db.get(LivraisonDB, livraison_id)
    if not l:
        raise HTTPException(status_code=404, detail="Livraison introuvable")

    ext = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Format d'image non supporté (jpeg, png, webp uniquement)")

    if l.preuve_url:
        _delete_preuve_file(l.preuve_url)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{livraison_id}-{uuid.uuid4().hex[:8]}{ext}"
    with open(UPLOADS_DIR / filename, "wb") as f:
        f.write(file.file.read())

    l.preuve_url = f"/uploads/livraisons/{filename}"
    db.commit()
    db.refresh(l)
    return l


@router.delete("/{livraison_id}/preuve", response_model=Livraison)
def supprimer_preuve(
    livraison_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> LivraisonDB:
    l = db.get(LivraisonDB, livraison_id)
    if not l:
        raise HTTPException(status_code=404, detail="Livraison introuvable")
    if l.preuve_url:
        _delete_preuve_file(l.preuve_url)
        l.preuve_url = None
        db.commit()
        db.refresh(l)
    return l
