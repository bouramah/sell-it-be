"""Validation d'une demande de crédit Aide Humanitaire par ses garants — endpoints publics
(aucune authentification KFSTORE) : le jeton unique envoyé par SMS EST l'authentification, cf.
app/services/validation_garant.py pour la création des jetons et l'envoi des SMS. La route
/admin/{id}/decision, elle, est authentifiée et réservée à l'administrateur — secours quand le
SMS n'est jamais arrivé au garant (cf. SECOURS_SMS_GESTION)."""
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import SECOURS_SMS_GESTION
from app.core.security import get_current_user
from app.db_models.models import BeneficiaireDB, DemandeCreditDB, UtilisateurDB, ValidationGarantCreditDB
from app.models.schemas import StatutValidationGarant, TypeGarant, ValidationGarantDecision, ValidationGarantDetail
from app.services.validation_garant import appliquer_decision_garant, now_naive

router = APIRouter(prefix="/api/v1/validation-garant", tags=["validation-garant"])


def _charger(db: Session, token: str) -> ValidationGarantCreditDB:
    v = db.query(ValidationGarantCreditDB).filter(ValidationGarantCreditDB.token == token).first()
    if not v:
        raise HTTPException(status_code=404, detail="Lien invalide")
    if v.expire_le < now_naive():
        raise HTTPException(status_code=410, detail="Ce lien de validation a expiré")
    return v


def _detail(db: Session, v: ValidationGarantCreditDB) -> ValidationGarantDetail:
    demande = db.get(DemandeCreditDB, v.demande_credit_id)
    beneficiaire = db.query(BeneficiaireDB).filter(BeneficiaireDB.client_id == demande.client_id).first()
    autre = (
        db.query(ValidationGarantCreditDB)
        .filter(ValidationGarantCreditDB.demande_credit_id == demande.id, ValidationGarantCreditDB.id != v.id)
        .first()
    )
    return ValidationGarantDetail(
        beneficiaire_nom=beneficiaire.client.nom, etablissement_nom=beneficiaire.etablissement.nom, poste=beneficiaire.poste,
        montant_souhaite=demande.montant_souhaite, motif=demande.motif,
        salaire_reference=beneficiaire.salaire_reference if v.type_garant == TypeGarant.comptabilite else None,
        type_garant=v.type_garant, statut=v.statut,
        autre_garant_statut=autre.statut if autre else StatutValidationGarant.en_attente,
        expire_le=v.expire_le,
    )


@router.get("/{token}", response_model=ValidationGarantDetail)
def consulter(token: str, db: Session = Depends(get_db)) -> ValidationGarantDetail:
    v = _charger(db, token)
    return _detail(db, v)


@router.post("/{token}", response_model=ValidationGarantDetail)
def repondre(token: str, payload: ValidationGarantDecision, db: Session = Depends(get_db)) -> ValidationGarantDetail:
    v = _charger(db, token)
    demande = db.get(DemandeCreditDB, v.demande_credit_id)
    beneficiaire = db.query(BeneficiaireDB).filter(BeneficiaireDB.client_id == demande.client_id).first()
    auteur = f"Garant {v.type_garant.value} — {beneficiaire.etablissement.nom}"
    try:
        appliquer_decision_garant(db, v, payload.approuve, payload.motif_refus, auteur)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.commit()
    db.refresh(v)
    return _detail(db, v)


@router.post("/admin/{validation_id}/decision", response_model=ValidationGarantDetail)
def repondre_admin(
    validation_id: str, payload: ValidationGarantDecision,
    db: Session = Depends(get_db), current_user: UtilisateurDB = Depends(get_current_user),
) -> ValidationGarantDetail:
    """Saisie manuelle par un administrateur à la place d'un garant injoignable (SMS jamais
    reçu) — la ligne reste tracée comme `validee_manuellement`, et `updated_by` porte le nom
    de l'administrateur, pas celui du garant (cf. SECOURS_SMS_GESTION)."""
    require_permission(db, current_user, SECOURS_SMS_GESTION)
    v = db.get(ValidationGarantCreditDB, validation_id)
    if not v:
        raise HTTPException(status_code=404, detail="Validation introuvable")

    demande = db.get(DemandeCreditDB, v.demande_credit_id)
    beneficiaire = db.query(BeneficiaireDB).filter(BeneficiaireDB.client_id == demande.client_id).first()
    nom_admin = f"{current_user.prenom} {current_user.nom}"
    auteur = f"{nom_admin} (validation manuelle admin, SMS indisponible) — au nom du garant {v.type_garant.value}"
    try:
        appliquer_decision_garant(db, v, payload.approuve, payload.motif_refus, auteur, updated_by=nom_admin, manuel=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.commit()
    db.refresh(v)
    return _detail(db, v)
