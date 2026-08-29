import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import BENEFICIAIRE_GESTION
from app.core.security import get_current_user
from app.db_models.models import BeneficiaireDB, BoutiqueDB, ClientDB, EtablissementDB, UtilisateurDB
from app.models.schemas import Beneficiaire, SegmentClient
from app.models.write_schemas import BeneficiaireCreate, BeneficiaireUpdate
from app.services.audit import log_audit
from app.services.bareme_credit import plafond_disponible
from app.services.carte_membre import generer_carte_membre_pdf
from app.services.validation_garant import creer_demande_credit_beneficiaire, DemandeCreditBeneficiaireInput

router = APIRouter(prefix="/api/v1/beneficiaires", tags=["beneficiaires"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "engagements"
ALLOWED_DOCUMENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}

ROLE_ADMINISTRATEUR = "administrateur"


def _delete_document_file(document_url: str) -> None:
    filename = document_url.rsplit("/", 1)[-1]
    path = UPLOADS_DIR / filename
    if path.exists():
        path.unlink()


def _to_schema(b: BeneficiaireDB, db: Session, current_user: UtilisateurDB) -> Beneficiaire:
    etablissement = db.get(EtablissementDB, b.etablissement_id)
    # Confidentialité : le salaire n'est jamais renvoyé hors administrateur — aucun rôle KFSTORE
    # ne représente la comptabilité d'un établissement précis (ce sont les garants, hors
    # authentification KFSTORE, qui y accèdent via leur jeton de validation).
    salaire = b.salaire_reference if current_user.role == ROLE_ADMINISTRATEUR else None
    return Beneficiaire(
        id=b.id, client_id=b.client_id, client_nom=b.client.nom, client_contact=b.client.contact,
        etablissement_id=b.etablissement_id, etablissement_nom=etablissement.nom if etablissement else b.etablissement_id,
        numero_membre=b.numero_membre, poste=b.poste,
        salaire_reference=salaire, engagement_signe_url=b.engagement_signe_url, engagement_signe_date=b.engagement_signe_date,
        plafond_suspendu=b.plafond_suspendu, plafond_disponible=plafond_disponible(db, b), credit_autorise=b.client.credit_autorise,
    )


def _nouveau_numero_membre(db: Session) -> str:
    compte = db.query(func.count(BeneficiaireDB.id)).scalar() or 0
    return f"KF-AH-{compte + 1:06d}"


@router.get("", response_model=list[Beneficiaire])
def list_beneficiaires(
    etablissement_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[Beneficiaire]:
    require_permission(db, current_user, BENEFICIAIRE_GESTION)
    query = db.query(BeneficiaireDB)
    if etablissement_id:
        query = query.filter(BeneficiaireDB.etablissement_id == etablissement_id)
    return [_to_schema(b, db, current_user) for b in query.all()]


@router.get("/{beneficiaire_id}", response_model=Beneficiaire)
def get_beneficiaire(
    beneficiaire_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Beneficiaire:
    require_permission(db, current_user, BENEFICIAIRE_GESTION)
    b = db.get(BeneficiaireDB, beneficiaire_id)
    if not b:
        raise HTTPException(status_code=404, detail="Bénéficiaire introuvable")
    return _to_schema(b, db, current_user)


@router.post("", response_model=Beneficiaire, status_code=201)
def create_beneficiaire(
    payload: BeneficiaireCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Beneficiaire:
    require_permission(db, current_user, BENEFICIAIRE_GESTION)
    if not db.get(EtablissementDB, payload.etablissement_id):
        raise HTTPException(status_code=404, detail="Établissement introuvable")
    auteur = f"{current_user.prenom} {current_user.nom}"

    if payload.client_id:
        client = db.get(ClientDB, payload.client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client introuvable")
        if db.query(BeneficiaireDB).filter(BeneficiaireDB.client_id == client.id).first():
            raise HTTPException(status_code=409, detail="Ce client est déjà rattaché à une fiche bénéficiaire")
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

    b = BeneficiaireDB(
        id=str(uuid.uuid4())[:8], client_id=client.id, etablissement_id=payload.etablissement_id,
        numero_membre=_nouveau_numero_membre(db), poste=payload.poste, salaire_reference=payload.salaire_reference,
        created_by=auteur, updated_by=auteur,
    )
    db.add(b)
    log_audit(db, f"Fiche bénéficiaire créée — {client.nom}", auteur)
    db.commit()
    db.refresh(b)
    return _to_schema(b, db, current_user)


@router.put("/{beneficiaire_id}", response_model=Beneficiaire)
def update_beneficiaire(
    beneficiaire_id: str,
    payload: BeneficiaireUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Beneficiaire:
    require_permission(db, current_user, BENEFICIAIRE_GESTION)
    b = db.get(BeneficiaireDB, beneficiaire_id)
    if not b:
        raise HTTPException(status_code=404, detail="Bénéficiaire introuvable")
    data = payload.model_dump(exclude_unset=True)
    if "etablissement_id" in data and not db.get(EtablissementDB, data["etablissement_id"]):
        raise HTTPException(status_code=404, detail="Établissement introuvable")
    for field, value in data.items():
        setattr(b, field, value)
    b.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(b)
    return _to_schema(b, db, current_user)


@router.post("/{beneficiaire_id}/engagement", response_model=Beneficiaire)
def uploader_engagement(
    beneficiaire_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Beneficiaire:
    """L'archivage de l'engagement signé conditionne l'activation du crédit — on réutilise
    directement credit_autorise (déjà le verrou du crédit générique) plutôt que d'introduire un
    second booléen qui pourrait diverger."""
    require_permission(db, current_user, BENEFICIAIRE_GESTION)
    b = db.get(BeneficiaireDB, beneficiaire_id)
    if not b:
        raise HTTPException(status_code=404, detail="Bénéficiaire introuvable")

    ext = ALLOWED_DOCUMENT_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Format non supporté (jpeg, png, webp, pdf uniquement)")

    if b.engagement_signe_url:
        _delete_document_file(b.engagement_signe_url)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{beneficiaire_id}-{uuid.uuid4().hex[:8]}{ext}"
    with open(UPLOADS_DIR / filename, "wb") as f:
        f.write(file.file.read())

    auteur = f"{current_user.prenom} {current_user.nom}"
    b.engagement_signe_url = f"/uploads/engagements/{filename}"
    b.engagement_signe_date = date.today()
    b.updated_by = auteur
    b.client.credit_autorise = True
    b.client.updated_by = auteur
    log_audit(db, f"Engagement signé enregistré — {b.client.nom}", auteur)
    db.commit()
    db.refresh(b)
    return _to_schema(b, db, current_user)


@router.delete("/{beneficiaire_id}/engagement", response_model=Beneficiaire)
def supprimer_engagement(
    beneficiaire_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Beneficiaire:
    require_permission(db, current_user, BENEFICIAIRE_GESTION)
    b = db.get(BeneficiaireDB, beneficiaire_id)
    if not b:
        raise HTTPException(status_code=404, detail="Bénéficiaire introuvable")
    if b.engagement_signe_url:
        _delete_document_file(b.engagement_signe_url)
        b.engagement_signe_url = None
        b.engagement_signe_date = None
        b.client.credit_autorise = False
        b.updated_by = f"{current_user.prenom} {current_user.nom}"
        db.commit()
        db.refresh(b)
    return _to_schema(b, db, current_user)


@router.post("/{beneficiaire_id}/demandes-credit", response_model=Beneficiaire, status_code=201)
def creer_demande_credit_pour_beneficiaire(
    beneficiaire_id: str,
    payload: DemandeCreditBeneficiaireInput,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Beneficiaire:
    """Demande créée par le staff pour un bénéficiaire qui se présente directement en boutique —
    passe par le même circuit de validation par les garants, le staff ne peut jamais activer le
    crédit lui-même."""
    require_permission(db, current_user, BENEFICIAIRE_GESTION)
    b = db.get(BeneficiaireDB, beneficiaire_id)
    if not b:
        raise HTTPException(status_code=404, detail="Bénéficiaire introuvable")
    try:
        creer_demande_credit_beneficiaire(db, b, payload, cree_par=f"{current_user.prenom} {current_user.nom} (boutique)")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(b)
    return _to_schema(b, db, current_user)


@router.get("/{beneficiaire_id}/carte-membre.pdf")
def carte_membre_pdf(
    beneficiaire_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Response:
    require_permission(db, current_user, BENEFICIAIRE_GESTION)
    b = db.get(BeneficiaireDB, beneficiaire_id)
    if not b:
        raise HTTPException(status_code=404, detail="Bénéficiaire introuvable")
    pdf_bytes = generer_carte_membre_pdf(
        nom_complet=b.client.nom, numero_membre=b.numero_membre,
        etablissement_nom=b.etablissement.nom, type_etablissement=b.etablissement.type_etablissement,
    )
    return Response(
        content=pdf_bytes, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="carte-membre-{b.numero_membre}.pdf"'},
    )
