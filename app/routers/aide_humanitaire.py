"""Suivi et rapprochement du module Aide Humanitaire — vue consolidée par établissement (crédits
en cours/en retard, versements reçus, écart), et enregistrement des versements groupés reçus
d'un établissement ("réconciliation entre crédits accordés par établissement et versements
reçus"). Un versement groupé n'a volontairement pas de correspondance 1:1 avec une DetteDB
(un seul virement peut couvrir plusieurs bénéficiaires) — cf. VersementEtablissementDB."""
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import BENEFICIAIRE_GESTION
from app.core.security import get_current_user
from app.db_models.models import BeneficiaireDB, DetteDB, EtablissementDB, UtilisateurDB, VersementEtablissementDB
from app.models.schemas import StatutDette, SuiviEtablissement, VersementEtablissement
from app.models.write_schemas import VersementEtablissementCreate

router = APIRouter(prefix="/api/v1/aide-humanitaire", tags=["aide-humanitaire"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "versements"
ALLOWED_DOCUMENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}


@router.get("/dashboard", response_model=list[SuiviEtablissement])
def dashboard(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[SuiviEtablissement]:
    require_permission(db, current_user, BENEFICIAIRE_GESTION)
    etablissements = db.query(EtablissementDB).all()
    resultat = []
    for e in etablissements:
        client_ids = [b.client_id for b in db.query(BeneficiaireDB).filter(BeneficiaireDB.etablissement_id == e.id).all()]
        dettes = db.query(DetteDB).filter(DetteDB.client_id.in_(client_ids)).all() if client_ids else []
        en_cours = sum(d.solde_restant for d in dettes if d.statut == StatutDette.en_cours)
        en_retard = sum(d.solde_restant for d in dettes if d.statut == StatutDette.en_retard)
        verse = sum(v.montant for v in db.query(VersementEtablissementDB).filter(VersementEtablissementDB.etablissement_id == e.id).all())
        credits_accordes = sum(d.montant_initial for d in dettes)
        resultat.append(SuiviEtablissement(
            etablissement_id=e.id, etablissement_nom=e.nom, nombre_beneficiaires=len(client_ids),
            credits_en_cours=en_cours, credits_en_retard=en_retard, montant_verse=verse,
            ecart=credits_accordes - verse,
        ))
    return resultat


@router.get("/versements", response_model=list[VersementEtablissement])
def list_versements(
    etablissement_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[VersementEtablissement]:
    require_permission(db, current_user, BENEFICIAIRE_GESTION)
    query = db.query(VersementEtablissementDB)
    if etablissement_id:
        query = query.filter(VersementEtablissementDB.etablissement_id == etablissement_id)
    etablissements_by_id = {e.id: e.nom for e in db.query(EtablissementDB).all()}
    return [
        VersementEtablissement(
            id=v.id, etablissement_id=v.etablissement_id, etablissement_nom=etablissements_by_id.get(v.etablissement_id, v.etablissement_id),
            montant=v.montant, date=v.date, reference=v.reference, justificatif_url=v.justificatif_url, note=v.note,
        )
        for v in query.all()
    ]


@router.post("/versements", response_model=VersementEtablissement, status_code=201)
def create_versement(
    payload: VersementEtablissementCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> VersementEtablissement:
    require_permission(db, current_user, BENEFICIAIRE_GESTION)
    etablissement = db.get(EtablissementDB, payload.etablissement_id)
    if not etablissement:
        raise HTTPException(status_code=404, detail="Établissement introuvable")
    auteur = f"{current_user.prenom} {current_user.nom}"
    v = VersementEtablissementDB(id=str(uuid.uuid4())[:8], created_by=auteur, updated_by=auteur, **payload.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return VersementEtablissement(
        id=v.id, etablissement_id=v.etablissement_id, etablissement_nom=etablissement.nom, montant=v.montant,
        date=v.date, reference=v.reference, justificatif_url=v.justificatif_url, note=v.note,
    )


@router.post("/versements/{versement_id}/justificatif", response_model=VersementEtablissement)
def uploader_justificatif_versement(
    versement_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> VersementEtablissement:
    require_permission(db, current_user, BENEFICIAIRE_GESTION)
    v = db.get(VersementEtablissementDB, versement_id)
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
    etablissement = db.get(EtablissementDB, v.etablissement_id)
    return VersementEtablissement(
        id=v.id, etablissement_id=v.etablissement_id, etablissement_nom=etablissement.nom if etablissement else v.etablissement_id,
        montant=v.montant, date=v.date, reference=v.reference, justificatif_url=v.justificatif_url, note=v.note,
    )
