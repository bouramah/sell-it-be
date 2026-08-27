import uuid
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import ENSEIGNANT_GESTION
from app.core.security import get_current_user
from app.db_models.models import BoutiqueDB, ClientDB, EcoleDB, EnseignantDB, UtilisateurDB
from app.models.schemas import Enseignant, SegmentClient
from app.models.write_schemas import EnseignantCreate, EnseignantUpdate
from app.services.audit import log_audit
from app.services.bareme_credit import plafond_disponible
from app.services.validation_garant import creer_demande_credit_enseignant, DemandeCreditEnseignantInput

router = APIRouter(prefix="/api/v1/enseignants", tags=["enseignants"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "engagements"
ALLOWED_DOCUMENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}

ROLE_ADMINISTRATEUR = "administrateur"


def _delete_document_file(document_url: str) -> None:
    filename = document_url.rsplit("/", 1)[-1]
    path = UPLOADS_DIR / filename
    if path.exists():
        path.unlink()


def _to_schema(e: EnseignantDB, db: Session, current_user: UtilisateurDB) -> Enseignant:
    ecole = db.get(EcoleDB, e.ecole_id)
    # Confidentialité : le salaire n'est jamais renvoyé hors administrateur — aucun rôle KFSTORE
    # ne représente la comptabilité d'une école précise (ce sont les garants, hors authentification
    # KFSTORE, qui y accèdent via leur jeton de validation — cf. validation_garant.py).
    salaire = e.salaire_reference if current_user.role == ROLE_ADMINISTRATEUR else None
    return Enseignant(
        id=e.id, client_id=e.client_id, client_nom=e.client.nom, client_contact=e.client.contact,
        ecole_id=e.ecole_id, ecole_nom=ecole.nom if ecole else e.ecole_id, grade_echelon=e.grade_echelon,
        salaire_reference=salaire, engagement_signe_url=e.engagement_signe_url, engagement_signe_date=e.engagement_signe_date,
        plafond_suspendu=e.plafond_suspendu, plafond_disponible=plafond_disponible(db, e), credit_autorise=e.client.credit_autorise,
    )


@router.get("", response_model=list[Enseignant])
def list_enseignants(
    ecole_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[Enseignant]:
    require_permission(db, current_user, ENSEIGNANT_GESTION)
    query = db.query(EnseignantDB)
    if ecole_id:
        query = query.filter(EnseignantDB.ecole_id == ecole_id)
    return [_to_schema(e, db, current_user) for e in query.all()]


@router.get("/{enseignant_id}", response_model=Enseignant)
def get_enseignant(
    enseignant_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Enseignant:
    require_permission(db, current_user, ENSEIGNANT_GESTION)
    e = db.get(EnseignantDB, enseignant_id)
    if not e:
        raise HTTPException(status_code=404, detail="Enseignant introuvable")
    return _to_schema(e, db, current_user)


@router.post("", response_model=Enseignant, status_code=201)
def create_enseignant(
    payload: EnseignantCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Enseignant:
    require_permission(db, current_user, ENSEIGNANT_GESTION)
    if not db.get(EcoleDB, payload.ecole_id):
        raise HTTPException(status_code=404, detail="École introuvable")
    auteur = f"{current_user.prenom} {current_user.nom}"

    if payload.client_id:
        client = db.get(ClientDB, payload.client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client introuvable")
        if db.query(EnseignantDB).filter(EnseignantDB.client_id == client.id).first():
            raise HTTPException(status_code=409, detail="Ce client est déjà rattaché à une fiche enseignant")
    else:
        if not payload.nom or not payload.contact:
            raise HTTPException(status_code=400, detail="Nom et contact sont requis pour créer un nouveau client")
        boutiques = db.query(BoutiqueDB).filter(BoutiqueDB.id.in_(payload.boutique_ids)).all()
        client = ClientDB(
            id=str(uuid.uuid4())[:8], nom=payload.nom, contact=payload.contact, boutiques=boutiques,
            segment=SegmentClient.nouveau, credit_autorise=False,
            created_by=auteur, updated_by=auteur,
        )
        db.add(client)
        db.flush()

    e = EnseignantDB(
        id=str(uuid.uuid4())[:8], client_id=client.id, ecole_id=payload.ecole_id,
        grade_echelon=payload.grade_echelon, salaire_reference=payload.salaire_reference,
        created_by=auteur, updated_by=auteur,
    )
    db.add(e)
    log_audit(db, f"Fiche enseignant créée — {client.nom}", auteur)
    db.commit()
    db.refresh(e)
    return _to_schema(e, db, current_user)


@router.put("/{enseignant_id}", response_model=Enseignant)
def update_enseignant(
    enseignant_id: str,
    payload: EnseignantUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Enseignant:
    require_permission(db, current_user, ENSEIGNANT_GESTION)
    e = db.get(EnseignantDB, enseignant_id)
    if not e:
        raise HTTPException(status_code=404, detail="Enseignant introuvable")
    data = payload.model_dump(exclude_unset=True)
    if "ecole_id" in data and not db.get(EcoleDB, data["ecole_id"]):
        raise HTTPException(status_code=404, detail="École introuvable")
    for field, value in data.items():
        setattr(e, field, value)
    e.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(e)
    return _to_schema(e, db, current_user)


@router.post("/{enseignant_id}/engagement", response_model=Enseignant)
def uploader_engagement(
    enseignant_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Enseignant:
    """L'archivage de l'engagement signé conditionne l'activation du crédit (CDC §5.2) — on
    réutilise directement credit_autorise (déjà le verrou du crédit générique) plutôt que
    d'introduire un second booléen qui pourrait diverger."""
    require_permission(db, current_user, ENSEIGNANT_GESTION)
    e = db.get(EnseignantDB, enseignant_id)
    if not e:
        raise HTTPException(status_code=404, detail="Enseignant introuvable")

    ext = ALLOWED_DOCUMENT_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Format non supporté (jpeg, png, webp, pdf uniquement)")

    if e.engagement_signe_url:
        _delete_document_file(e.engagement_signe_url)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{enseignant_id}-{uuid.uuid4().hex[:8]}{ext}"
    with open(UPLOADS_DIR / filename, "wb") as f:
        f.write(file.file.read())

    auteur = f"{current_user.prenom} {current_user.nom}"
    e.engagement_signe_url = f"/uploads/engagements/{filename}"
    e.engagement_signe_date = date.today()
    e.updated_by = auteur
    e.client.credit_autorise = True
    e.client.updated_by = auteur
    log_audit(db, f"Engagement signé enregistré — {e.client.nom}", auteur)
    db.commit()
    db.refresh(e)
    return _to_schema(e, db, current_user)


@router.delete("/{enseignant_id}/engagement", response_model=Enseignant)
def supprimer_engagement(
    enseignant_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Enseignant:
    require_permission(db, current_user, ENSEIGNANT_GESTION)
    e = db.get(EnseignantDB, enseignant_id)
    if not e:
        raise HTTPException(status_code=404, detail="Enseignant introuvable")
    if e.engagement_signe_url:
        _delete_document_file(e.engagement_signe_url)
        e.engagement_signe_url = None
        e.engagement_signe_date = None
        e.client.credit_autorise = False
        e.updated_by = f"{current_user.prenom} {current_user.nom}"
        db.commit()
        db.refresh(e)
    return _to_schema(e, db, current_user)


@router.post("/{enseignant_id}/demandes-credit", response_model=Enseignant, status_code=201)
def creer_demande_credit_pour_enseignant(
    enseignant_id: str,
    payload: DemandeCreditEnseignantInput,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Enseignant:
    """Demande créée par le staff pour un enseignant qui se présente directement en boutique
    (CDC §4.2 : "en boutique ou via l'application") — passe par le même circuit de validation
    par les garants, le staff ne peut jamais activer le crédit lui-même."""
    require_permission(db, current_user, ENSEIGNANT_GESTION)
    e = db.get(EnseignantDB, enseignant_id)
    if not e:
        raise HTTPException(status_code=404, detail="Enseignant introuvable")
    try:
        creer_demande_credit_enseignant(db, e, payload, cree_par=f"{current_user.prenom} {current_user.nom} (boutique)")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(e)
    return _to_schema(e, db, current_user)
