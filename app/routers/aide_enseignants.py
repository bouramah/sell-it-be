"""Suivi et rapprochement du module Aide aux Enseignants — vue consolidée par école (crédits
en cours/en retard, versements reçus, écart), et enregistrement des versements groupés reçus
d'une école (CDC §4.5/§5.4 : "réconciliation entre crédits accordés par école et versements
reçus"). Un versement groupé n'a volontairement pas de correspondance 1:1 avec une DetteDB
(un seul virement peut couvrir plusieurs enseignants) — cf. VersementEcoleDB."""
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import ENSEIGNANT_GESTION
from app.core.security import get_current_user
from app.db_models.models import DetteDB, EcoleDB, EnseignantDB, UtilisateurDB, VersementEcoleDB
from app.models.schemas import StatutDette, SuiviEcole, VersementEcole
from app.models.write_schemas import VersementEcoleCreate

router = APIRouter(prefix="/api/v1/aide-enseignants", tags=["aide-enseignants"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "versements"
ALLOWED_DOCUMENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}


@router.get("/dashboard", response_model=list[SuiviEcole])
def dashboard(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[SuiviEcole]:
    require_permission(db, current_user, ENSEIGNANT_GESTION)
    ecoles = db.query(EcoleDB).all()
    resultat = []
    for e in ecoles:
        client_ids = [en.client_id for en in db.query(EnseignantDB).filter(EnseignantDB.ecole_id == e.id).all()]
        dettes = db.query(DetteDB).filter(DetteDB.client_id.in_(client_ids)).all() if client_ids else []
        en_cours = sum(d.solde_restant for d in dettes if d.statut == StatutDette.en_cours)
        en_retard = sum(d.solde_restant for d in dettes if d.statut == StatutDette.en_retard)
        verse = sum(v.montant for v in db.query(VersementEcoleDB).filter(VersementEcoleDB.ecole_id == e.id).all())
        credits_accordes = sum(d.montant_initial for d in dettes)
        resultat.append(SuiviEcole(
            ecole_id=e.id, ecole_nom=e.nom, nombre_enseignants=len(client_ids),
            credits_en_cours=en_cours, credits_en_retard=en_retard, montant_verse=verse,
            ecart=credits_accordes - verse,
        ))
    return resultat


@router.get("/versements", response_model=list[VersementEcole])
def list_versements(
    ecole_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[VersementEcole]:
    require_permission(db, current_user, ENSEIGNANT_GESTION)
    query = db.query(VersementEcoleDB)
    if ecole_id:
        query = query.filter(VersementEcoleDB.ecole_id == ecole_id)
    ecoles_by_id = {e.id: e.nom for e in db.query(EcoleDB).all()}
    return [
        VersementEcole(
            id=v.id, ecole_id=v.ecole_id, ecole_nom=ecoles_by_id.get(v.ecole_id, v.ecole_id), montant=v.montant,
            date=v.date, reference=v.reference, justificatif_url=v.justificatif_url, note=v.note,
        )
        for v in query.all()
    ]


@router.post("/versements", response_model=VersementEcole, status_code=201)
def create_versement(
    payload: VersementEcoleCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> VersementEcole:
    require_permission(db, current_user, ENSEIGNANT_GESTION)
    ecole = db.get(EcoleDB, payload.ecole_id)
    if not ecole:
        raise HTTPException(status_code=404, detail="École introuvable")
    auteur = f"{current_user.prenom} {current_user.nom}"
    v = VersementEcoleDB(id=str(uuid.uuid4())[:8], created_by=auteur, updated_by=auteur, **payload.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return VersementEcole(
        id=v.id, ecole_id=v.ecole_id, ecole_nom=ecole.nom, montant=v.montant,
        date=v.date, reference=v.reference, justificatif_url=v.justificatif_url, note=v.note,
    )


@router.post("/versements/{versement_id}/justificatif", response_model=VersementEcole)
def uploader_justificatif_versement(
    versement_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> VersementEcole:
    require_permission(db, current_user, ENSEIGNANT_GESTION)
    v = db.get(VersementEcoleDB, versement_id)
    if not v:
        raise HTTPException(status_code=404, detail="Versement introuvable")

    ext = ALLOWED_DOCUMENT_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Format non supporté (jpeg, png, webp, pdf uniquement)")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{versement_id}-{uuid.uuid4().hex[:8]}{ext}"
    with open(UPLOADS_DIR / filename, "wb") as f:
        f.write(file.file.read())

    v.justificatif_url = f"/uploads/versements/{filename}"
    v.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(v)
    ecole = db.get(EcoleDB, v.ecole_id)
    return VersementEcole(
        id=v.id, ecole_id=v.ecole_id, ecole_nom=ecole.nom if ecole else v.ecole_id, montant=v.montant,
        date=v.date, reference=v.reference, justificatif_url=v.justificatif_url, note=v.note,
    )
