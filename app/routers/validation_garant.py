"""Validation d'une demande de crédit enseignant par ses garants — endpoints publics (aucune
authentification KFSTORE) : le jeton unique envoyé par SMS EST l'authentification, cf.
app/services/validation_garant.py pour la création des jetons et l'envoi des SMS."""
import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.db_models.models import DemandeCreditDB, DetteDB, EnseignantDB, ValidationGarantCreditDB
from app.models.schemas import StatutDemandeCredit, StatutDette, StatutValidationGarant, TiersType, TypeGarant, ValidationGarantDecision, ValidationGarantDetail
from app.services.audit import log_audit
from app.services.notifications import notifier_client
from app.services.validation_garant import now_naive

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
    enseignant = db.query(EnseignantDB).filter(EnseignantDB.client_id == demande.client_id).first()
    autre = (
        db.query(ValidationGarantCreditDB)
        .filter(ValidationGarantCreditDB.demande_credit_id == demande.id, ValidationGarantCreditDB.id != v.id)
        .first()
    )
    return ValidationGarantDetail(
        enseignant_nom=enseignant.client.nom, ecole_nom=enseignant.ecole.nom, grade_echelon=enseignant.grade_echelon,
        montant_souhaite=demande.montant_souhaite, motif=demande.motif,
        salaire_reference=enseignant.salaire_reference if v.type_garant == TypeGarant.comptabilite else None,
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
    if v.statut != StatutValidationGarant.en_attente:
        raise HTTPException(status_code=400, detail="Cette demande a déjà reçu votre réponse")
    if not payload.approuve and not payload.motif_refus:
        raise HTTPException(status_code=400, detail="Un motif est requis en cas de refus")

    v.statut = StatutValidationGarant.validee if payload.approuve else StatutValidationGarant.refusee
    v.date_reponse = now_naive()
    v.motif_refus = payload.motif_refus if not payload.approuve else None

    demande = db.get(DemandeCreditDB, v.demande_credit_id)
    enseignant = db.query(EnseignantDB).filter(EnseignantDB.client_id == demande.client_id).first()
    toutes = db.query(ValidationGarantCreditDB).filter(ValidationGarantCreditDB.demande_credit_id == demande.id).all()
    auteur = f"Garant {v.type_garant.value} — {enseignant.ecole.nom}"

    if any(a.statut == StatutValidationGarant.refusee for a in toutes):
        demande.statut = StatutDemandeCredit.refusee
        demande.updated_by = auteur
        log_audit(db, f"Demande de crédit enseignant refusée par un garant — {enseignant.client.nom}", auteur, demande.boutique_id)
        notifier_client(
            db, enseignant.client.nom,
            f"KFSTORE — Votre demande de crédit alimentaire de {demande.montant_souhaite:,.0f} GNF a été refusée "
            f"par un de vos garants.".replace(",", " "),
        )
    elif all(a.statut == StatutValidationGarant.validee for a in toutes):
        demande.statut = StatutDemandeCredit.validee
        demande.updated_by = auteur
        dette = DetteDB(
            id=str(uuid.uuid4())[:8], tiers_type=TiersType.client, tiers_nom=enseignant.client.nom, client_id=enseignant.client_id,
            boutique_id=demande.boutique_id, montant_initial=demande.montant_souhaite, solde_restant=demande.montant_souhaite,
            echeance=date.today() + timedelta(days=30), statut=StatutDette.en_cours, demande_credit_id=demande.id,
            created_by=auteur, updated_by=auteur,
        )
        db.add(dette)
        log_audit(db, f"Crédit enseignant activé (2 garants validés) — {enseignant.client.nom} ({demande.montant_souhaite:,.0f} GNF)".replace(",", " "), auteur, demande.boutique_id)
        notifier_client(
            db, enseignant.client.nom,
            f"KFSTORE — Votre crédit alimentaire de {demande.montant_souhaite:,.0f} GNF est activé, vous pouvez "
            f"retirer vos denrées en boutique. Remboursement à échéance du {dette.echeance.strftime('%d/%m/%Y')}.".replace(",", " "),
        )

    db.commit()
    db.refresh(v)
    return _detail(db, v)
