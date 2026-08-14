import uuid
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.core.authorization import assert_boutique_access, require_permission
from app.core.database import get_db
from app.core.db_errors import commit_or_409
from app.core.module_actions import FOURNISSEUR_GESTION, PRODUIT_GESTION
from app.core.security import get_current_user
from app.db_models.models import FournisseurDB, PrixAchatDB, PrixPeriodeDB, ProduitDB, ProduitImageDB, UtilisateurDB
from app.models.schemas import PalierPrix, PrixAchat, PrixPeriode, Produit, ProduitImage
from app.models.write_schemas import PrixAchatInput, PrixPeriodeInput, ProduitCreate, ProduitUpdate
from app.services.audit import log_audit
from app.services.pricing import (
    prix_achat_effectif_a_date,
    prix_effectif_a_date,
    verifier_chevauchement,
    verifier_chevauchement_achat,
)

router = APIRouter(prefix="/api/v1/produits", tags=["produits"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "produits"
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def _to_schema(db: Session, p: ProduitDB) -> Produit:
    today = date.today()
    return Produit(
        id=p.id, nom=p.nom, secteur=p.secteur, categorie=p.categorie,
        prix_detail=prix_effectif_a_date(db, p.id, None, PalierPrix.detail, today) or 0.0,
        prix_semi_gros=prix_effectif_a_date(db, p.id, None, PalierPrix.semi_gros, today) or 0.0,
        prix_gros=prix_effectif_a_date(db, p.id, None, PalierPrix.gros, today) or 0.0,
        seuil_semi_gros=p.seuil_semi_gros, seuil_gros=p.seuil_gros, unite=p.unite,
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
    return [_to_schema(db, p) for p in query.all()]


@router.get("/{produit_id}", response_model=Produit)
def get_produit(produit_id: str, db: Session = Depends(get_db)) -> Produit:
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    return _to_schema(db, p)


@router.post("", response_model=Produit, status_code=201)
def create_produit(
    payload: ProduitCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Produit:
    require_permission(db, current_user, PRODUIT_GESTION)
    if db.query(ProduitDB).filter(ProduitDB.code_barres == payload.code_barres).first():
        raise HTTPException(status_code=409, detail="Un produit avec ce code-barres existe déjà")
    data = payload.model_dump()
    prix_initiaux = {
        PalierPrix.detail: data.pop("prix_detail"),
        PalierPrix.semi_gros: data.pop("prix_semi_gros"),
        PalierPrix.gros: data.pop("prix_gros"),
    }
    modifie_par = f"{current_user.prenom} {current_user.nom}"
    p = ProduitDB(id=str(uuid.uuid4())[:8], created_by=modifie_par, updated_by=modifie_par, **data)
    db.add(p)
    db.flush()

    today = date.today()
    for palier, prix in prix_initiaux.items():
        db.add(PrixPeriodeDB(
            id=str(uuid.uuid4())[:8], produit_id=p.id, boutique_id=None, palier=palier,
            prix=prix, date_debut=today, date_fin=None, modifie_par=modifie_par,
        ))

    db.commit()
    db.refresh(p)
    return _to_schema(db, p)


@router.put("/{produit_id}", response_model=Produit)
def update_produit(
    produit_id: str,
    payload: ProduitUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Produit:
    require_permission(db, current_user, PRODUIT_GESTION)
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    p.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(p)
    return _to_schema(db, p)


@router.delete("/{produit_id}", status_code=204)
def delete_produit(
    produit_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, PRODUIT_GESTION)
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    for img in p.images:
        _delete_image_file(img.url)
    db.delete(p)
    commit_or_409(db, "Impossible de supprimer ce produit : il a du stock ou un historique de mouvements/commandes.")


@router.post("/{produit_id}/images", response_model=Produit)
def uploader_image(
    produit_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Produit:
    require_permission(db, current_user, PRODUIT_GESTION)
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
    auteur = f"{current_user.prenom} {current_user.nom}"
    db.add(ProduitImageDB(id=str(uuid.uuid4())[:8], produit_id=produit_id, url=f"/uploads/produits/{filename}", position=next_position, created_by=auteur, updated_by=auteur))
    db.commit()
    db.refresh(p)
    return _to_schema(db, p)


@router.delete("/{produit_id}/images/{image_id}", response_model=Produit)
def supprimer_image(
    produit_id: str,
    image_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Produit:
    require_permission(db, current_user, PRODUIT_GESTION)
    p = db.get(ProduitDB, produit_id)
    if not p:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    img = db.get(ProduitImageDB, image_id)
    if img and img.produit_id == produit_id:
        _delete_image_file(img.url)
        db.delete(img)
        db.commit()
        db.refresh(p)
    return _to_schema(db, p)


@router.get("/{produit_id}/prix-periodes", response_model=list[PrixPeriode])
def list_prix_periodes(
    produit_id: str,
    boutique_id: str | None = None,
    palier: PalierPrix | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[PrixPeriodeDB]:
    if not db.get(ProduitDB, produit_id):
        raise HTTPException(status_code=404, detail="Produit introuvable")
    query = db.query(PrixPeriodeDB).filter(PrixPeriodeDB.produit_id == produit_id)
    if boutique_id:
        query = query.filter(PrixPeriodeDB.boutique_id == boutique_id)
    if palier:
        query = query.filter(PrixPeriodeDB.palier == palier)
    return sorted(query.all(), key=lambda r: r.date_debut, reverse=True)


@router.get("/{produit_id}/prix-a-date", response_model=dict[str, float | None])
def prix_a_date(
    produit_id: str,
    a_date: date,
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> dict[str, float | None]:
    """Prix des 3 paliers applicables à une date donnée — pour auditer une vente passée
    (comparer le prix facturé au prix catalogue en vigueur ce jour-là)."""
    if not db.get(ProduitDB, produit_id):
        raise HTTPException(status_code=404, detail="Produit introuvable")
    return {
        palier.value: prix_effectif_a_date(db, produit_id, boutique_id, palier, a_date)
        for palier in PalierPrix
    }


@router.post("/{produit_id}/prix-periodes", response_model=PrixPeriode, status_code=201)
def creer_prix_periode(
    produit_id: str,
    payload: PrixPeriodeInput,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PrixPeriodeDB:
    require_permission(db, current_user, PRODUIT_GESTION)
    if payload.boutique_id:
        assert_boutique_access(current_user, payload.boutique_id)
    if not db.get(ProduitDB, produit_id):
        raise HTTPException(status_code=404, detail="Produit introuvable")
    if payload.date_fin is not None and payload.date_fin < payload.date_debut:
        raise HTTPException(status_code=400, detail="La date de fin doit être postérieure à la date de début")

    conflit = verifier_chevauchement(db, produit_id, payload.boutique_id, payload.palier, payload.date_debut, payload.date_fin)
    if conflit:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Chevauchement avec une période existante du {conflit.date_debut} "
                f"au {conflit.date_fin or '…'} — fermez-la d'abord (date de fin) avant d'en ajouter une nouvelle."
            ),
        )

    modifie_par = f"{current_user.prenom} {current_user.nom}"
    periode = PrixPeriodeDB(
        id=str(uuid.uuid4())[:8], produit_id=produit_id, boutique_id=payload.boutique_id,
        palier=payload.palier, prix=payload.prix, date_debut=payload.date_debut, date_fin=payload.date_fin,
        modifie_par=modifie_par,
    )
    db.add(periode)

    produit = db.get(ProduitDB, produit_id)
    portee = "réseau" if not payload.boutique_id else f"boutique {payload.boutique_id}"
    log_audit(
        db,
        f"Nouveau prix {payload.palier.value} pour {produit.nom} ({portee}) : {payload.prix:,.0f} GNF "
        f"à partir du {payload.date_debut}".replace(",", " "),
        modifie_par, payload.boutique_id,
    )
    db.commit()
    db.refresh(periode)
    return periode


@router.put("/{produit_id}/prix-periodes/{periode_id}", response_model=PrixPeriode)
def modifier_prix_periode(
    produit_id: str,
    periode_id: str,
    payload: PrixPeriodeInput,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PrixPeriodeDB:
    require_permission(db, current_user, PRODUIT_GESTION)
    periode = db.get(PrixPeriodeDB, periode_id)
    if not periode or periode.produit_id != produit_id:
        raise HTTPException(status_code=404, detail="Période de prix introuvable")
    if payload.boutique_id:
        assert_boutique_access(current_user, payload.boutique_id)
    if payload.date_fin is not None and payload.date_fin < payload.date_debut:
        raise HTTPException(status_code=400, detail="La date de fin doit être postérieure à la date de début")

    conflit = verifier_chevauchement(db, produit_id, payload.boutique_id, payload.palier, payload.date_debut, payload.date_fin, exclure_id=periode_id)
    if conflit:
        raise HTTPException(
            status_code=409,
            detail=f"Chevauchement avec une période existante du {conflit.date_debut} au {conflit.date_fin or '…'}",
        )

    periode.boutique_id = payload.boutique_id
    periode.palier = payload.palier
    periode.prix = payload.prix
    periode.date_debut = payload.date_debut
    periode.date_fin = payload.date_fin
    periode.modifie_par = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(periode)
    return periode


@router.delete("/{produit_id}/prix-periodes/{periode_id}", status_code=204)
def supprimer_prix_periode(
    produit_id: str,
    periode_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, PRODUIT_GESTION)
    periode = db.get(PrixPeriodeDB, periode_id)
    if not periode or periode.produit_id != produit_id:
        raise HTTPException(status_code=404, detail="Période de prix introuvable")
    if periode.boutique_id:
        assert_boutique_access(current_user, periode.boutique_id)
    db.delete(periode)
    db.commit()


# --- Prix d'achat (fournisseur) ------------------------------------------------------------
# Un fournisseur peut consentir un meilleur prix selon le volume acheté — même principe de
# périodes datées et sans chevauchement que les prix de vente, mais toujours rattaché à un
# fournisseur précis (pas de "prix réseau" côté achat).

@router.get("/{produit_id}/prix-achat", response_model=list[PrixAchat])
def list_prix_achat(
    produit_id: str,
    fournisseur_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[PrixAchatDB]:
    if not db.get(ProduitDB, produit_id):
        raise HTTPException(status_code=404, detail="Produit introuvable")
    query = db.query(PrixAchatDB).filter(PrixAchatDB.produit_id == produit_id)
    if fournisseur_id:
        query = query.filter(PrixAchatDB.fournisseur_id == fournisseur_id)
    return sorted(query.all(), key=lambda r: r.date_debut, reverse=True)


@router.post("/{produit_id}/prix-achat", response_model=PrixAchat, status_code=201)
def creer_prix_achat(
    produit_id: str,
    payload: PrixAchatInput,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PrixAchatDB:
    require_permission(db, current_user, FOURNISSEUR_GESTION)
    if not db.get(ProduitDB, produit_id):
        raise HTTPException(status_code=404, detail="Produit introuvable")
    if not db.get(FournisseurDB, payload.fournisseur_id):
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    if payload.date_fin is not None and payload.date_fin < payload.date_debut:
        raise HTTPException(status_code=400, detail="La date de fin doit être postérieure à la date de début")

    conflit = verifier_chevauchement_achat(db, produit_id, payload.fournisseur_id, payload.palier, payload.date_debut, payload.date_fin)
    if conflit:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Chevauchement avec un prix d'achat existant du {conflit.date_debut} "
                f"au {conflit.date_fin or '…'} — fermez-le d'abord (date de fin) avant d'en ajouter un nouveau."
            ),
        )

    modifie_par = f"{current_user.prenom} {current_user.nom}"
    achat = PrixAchatDB(
        id=str(uuid.uuid4())[:8], produit_id=produit_id, fournisseur_id=payload.fournisseur_id,
        palier=payload.palier, prix=payload.prix, date_debut=payload.date_debut, date_fin=payload.date_fin,
        modifie_par=modifie_par,
    )
    db.add(achat)

    produit = db.get(ProduitDB, produit_id)
    fournisseur = db.get(FournisseurDB, payload.fournisseur_id)
    log_audit(
        db,
        f"Nouveau prix d'achat {payload.palier.value} pour {produit.nom} auprès de {fournisseur.nom} : "
        f"{payload.prix:,.0f} GNF à partir du {payload.date_debut}".replace(",", " "),
        modifie_par, None,
    )
    db.commit()
    db.refresh(achat)
    return achat


@router.put("/{produit_id}/prix-achat/{achat_id}", response_model=PrixAchat)
def modifier_prix_achat(
    produit_id: str,
    achat_id: str,
    payload: PrixAchatInput,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PrixAchatDB:
    require_permission(db, current_user, FOURNISSEUR_GESTION)
    achat = db.get(PrixAchatDB, achat_id)
    if not achat or achat.produit_id != produit_id:
        raise HTTPException(status_code=404, detail="Prix d'achat introuvable")
    if payload.date_fin is not None and payload.date_fin < payload.date_debut:
        raise HTTPException(status_code=400, detail="La date de fin doit être postérieure à la date de début")

    conflit = verifier_chevauchement_achat(db, produit_id, payload.fournisseur_id, payload.palier, payload.date_debut, payload.date_fin, exclure_id=achat_id)
    if conflit:
        raise HTTPException(
            status_code=409,
            detail=f"Chevauchement avec un prix d'achat existant du {conflit.date_debut} au {conflit.date_fin or '…'}",
        )

    achat.fournisseur_id = payload.fournisseur_id
    achat.palier = payload.palier
    achat.prix = payload.prix
    achat.date_debut = payload.date_debut
    achat.date_fin = payload.date_fin
    achat.modifie_par = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(achat)
    return achat


@router.delete("/{produit_id}/prix-achat/{achat_id}", status_code=204)
def supprimer_prix_achat(
    produit_id: str,
    achat_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, FOURNISSEUR_GESTION)
    achat = db.get(PrixAchatDB, achat_id)
    if not achat or achat.produit_id != produit_id:
        raise HTTPException(status_code=404, detail="Prix d'achat introuvable")
    db.delete(achat)
    db.commit()
