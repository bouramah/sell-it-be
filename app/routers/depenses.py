import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.core.authorization import ROLES_PORTEE_RESEAU, apply_boutique_filter, assert_boutique_access, require_role
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import CaisseDB, DepenseDB, MouvementCaisseDB, UtilisateurDB
from app.models.schemas import Depense, Role, StatutCaisse, StatutValidationDepense, TypeMouvementCaisse
from app.models.write_schemas import DepenseCreate
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/depenses", tags=["depenses"])

# Au-delà de ce montant, une dépense doit être validée par le siège (double validation, cf. CDC anti-fraude).
SEUIL_VALIDATION_SIEGE = 500_000

# CDC 3.3 : "Enregistrer une dépense de boutique" = gérant (+ administrateur) seulement.
ROLES_DEPENSE_CREATION = (Role.gerant, Role.administrateur)

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "depenses"
ALLOWED_DOCUMENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}


def _delete_justificatif_file(url: str) -> None:
    filename = url.rsplit("/", 1)[-1]
    path = UPLOADS_DIR / filename
    if path.exists():
        path.unlink()


@router.get("", response_model=list[Depense])
def list_depenses(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[DepenseDB]:
    query = apply_boutique_filter(db.query(DepenseDB), DepenseDB.boutique_id, current_user, boutique_id)
    return query.all()


@router.post("", response_model=Depense, status_code=201)
def create_depense(
    payload: DepenseCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> DepenseDB:
    require_role(current_user, *ROLES_DEPENSE_CREATION)
    assert_boutique_access(current_user, payload.boutique_id)
    caisse = db.get(CaisseDB, payload.caisse_id)
    if not caisse:
        raise HTTPException(status_code=404, detail="Caisse introuvable")
    if caisse.boutique_id != payload.boutique_id:
        raise HTTPException(status_code=400, detail="Cette caisse n'appartient pas à la boutique sélectionnée")
    if caisse.statut != StatutCaisse.ouverte:
        raise HTTPException(status_code=400, detail="La caisse doit être ouverte pour enregistrer une dépense")

    statut = (
        StatutValidationDepense.auto_validee
        if payload.montant < SEUIL_VALIDATION_SIEGE
        else StatutValidationDepense.en_attente
    )
    d = DepenseDB(
        id=str(uuid.uuid4())[:8], boutique_id=payload.boutique_id, caisse_id=payload.caisse_id,
        categorie=payload.categorie, auteur=payload.auteur, date=payload.date, montant=payload.montant,
        statut_validation=statut,
    )
    db.add(d)

    db.add(MouvementCaisseDB(
        id=str(uuid.uuid4())[:8], horodatage=datetime.now(timezone.utc), boutique_id=caisse.boutique_id,
        caisse_id=caisse.id, caisse_libelle=caisse.libelle, type=TypeMouvementCaisse.decaissement,
        motif=f"Dépense — {payload.categorie}", operateur=payload.auteur, montant=-payload.montant,
    ))
    caisse.solde_theorique -= payload.montant

    db.commit()
    db.refresh(d)
    return d


@router.post("/{depense_id}/valider", response_model=Depense)
def valider_depense(
    depense_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> DepenseDB:
    d = db.get(DepenseDB, depense_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dépense introuvable")
    require_role(current_user, *ROLES_PORTEE_RESEAU)
    if d.statut_validation != StatutValidationDepense.en_attente:
        raise HTTPException(status_code=400, detail="Cette dépense n'est pas en attente de validation")
    d.statut_validation = StatutValidationDepense.validee_siege
    log_audit(
        db,
        f"Dépense validée — {d.categorie} {d.montant:,.0f} GNF".replace(",", " "),
        f"{current_user.prenom} {current_user.nom}",
        d.boutique_id,
    )
    db.commit()
    db.refresh(d)
    return d


@router.post("/{depense_id}/justificatif", response_model=Depense)
def uploader_justificatif(
    depense_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> DepenseDB:
    d = db.get(DepenseDB, depense_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dépense introuvable")
    require_role(current_user, *ROLES_DEPENSE_CREATION)
    assert_boutique_access(current_user, d.boutique_id)

    ext = ALLOWED_DOCUMENT_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Format non supporté (jpeg, png, webp, pdf uniquement)")

    if d.justificatif_url:
        _delete_justificatif_file(d.justificatif_url)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{depense_id}-{uuid.uuid4().hex[:8]}{ext}"
    with open(UPLOADS_DIR / filename, "wb") as f:
        f.write(file.file.read())

    d.justificatif_url = f"/uploads/depenses/{filename}"
    db.commit()
    db.refresh(d)
    return d


@router.delete("/{depense_id}/justificatif", response_model=Depense)
def supprimer_justificatif(
    depense_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> DepenseDB:
    d = db.get(DepenseDB, depense_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dépense introuvable")
    require_role(current_user, *ROLES_DEPENSE_CREATION)
    assert_boutique_access(current_user, d.boutique_id)
    if d.justificatif_url:
        _delete_justificatif_file(d.justificatif_url)
        d.justificatif_url = None
        db.commit()
        db.refresh(d)
    return d
