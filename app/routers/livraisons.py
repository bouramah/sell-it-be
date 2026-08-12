import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.core.authorization import apply_boutique_filter, assert_boutique_access, require_permission
from app.core.database import get_db
from app.core.module_actions import LIVRAISON_GESTION
from app.core.security import get_current_user
from app.db_models.models import CommandeClientDB, LivraisonDB, UtilisateurDB
from app.models.schemas import Livraison, StatutCommandeClient, StatutLivraison
from app.models.write_schemas import LivraisonCreate, LivraisonStatutUpdate
from app.services.notifications import nom_boutique, notifier_client

router = APIRouter(prefix="/api/v1/livraisons", tags=["livraisons"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "livraisons"
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _delete_preuve_file(url: str) -> None:
    filename = url.rsplit("/", 1)[-1]
    path = UPLOADS_DIR / filename
    if path.exists():
        path.unlink()


@router.get("", response_model=list[Livraison])
def list_livraisons(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[LivraisonDB]:
    query = apply_boutique_filter(db.query(LivraisonDB), LivraisonDB.boutique_id, current_user, boutique_id)
    return query.all()


@router.post("", response_model=Livraison, status_code=201)
def create_livraison(
    payload: LivraisonCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LivraisonDB:
    require_permission(db, current_user, LIVRAISON_GESTION)
    assert_boutique_access(current_user, payload.boutique_id)
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

    notifier_client(
        db, commande.client_nom,
        f"Bonjour {commande.client_nom}, votre commande #{commande.id} a été affectée à un livreur. "
        f"Créneau : {l.creneau}. Adresse : {l.adresse}. — KFSTORE",
    )

    return l


@router.put("/{livraison_id}/statut", response_model=Livraison)
def update_statut(
    livraison_id: str,
    payload: LivraisonStatutUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LivraisonDB:
    l = db.get(LivraisonDB, livraison_id)
    if not l:
        raise HTTPException(status_code=404, detail="Livraison introuvable")
    require_permission(db, current_user, LIVRAISON_GESTION)
    assert_boutique_access(current_user, l.boutique_id)
    l.statut = payload.statut
    commande = db.get(CommandeClientDB, l.commande_id)
    if payload.statut == StatutLivraison.livree:
        if commande and commande.statut != StatutCommandeClient.annulee:
            commande.statut = StatutCommandeClient.livree
    db.commit()
    db.refresh(l)

    if commande and payload.statut == StatutLivraison.livree:
        notifier_client(
            db, commande.client_nom,
            f"Bonjour {commande.client_nom}, votre commande #{commande.id} a été livrée avec succès. "
            f"Merci de votre confiance ! — KFSTORE",
        )
    elif commande and payload.statut == StatutLivraison.echec:
        notifier_client(
            db, commande.client_nom,
            f"Bonjour {commande.client_nom}, la livraison de votre commande #{commande.id} a rencontré un problème. "
            f"La boutique {nom_boutique(db, l.boutique_id)} va vous recontacter. — KFSTORE",
        )

    return l


@router.post("/{livraison_id}/preuve", response_model=Livraison)
def uploader_preuve(
    livraison_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LivraisonDB:
    l = db.get(LivraisonDB, livraison_id)
    if not l:
        raise HTTPException(status_code=404, detail="Livraison introuvable")
    require_permission(db, current_user, LIVRAISON_GESTION)
    assert_boutique_access(current_user, l.boutique_id)

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
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LivraisonDB:
    l = db.get(LivraisonDB, livraison_id)
    if not l:
        raise HTTPException(status_code=404, detail="Livraison introuvable")
    require_permission(db, current_user, LIVRAISON_GESTION)
    assert_boutique_access(current_user, l.boutique_id)
    if l.preuve_url:
        _delete_preuve_file(l.preuve_url)
        l.preuve_url = None
        db.commit()
        db.refresh(l)
    return l
