"""Circuit de validation par les garants (référent + comptabilité de l'établissement) pour une
demande de crédit Aide Humanitaire — remplace la validation staff utilisée pour le crédit client
générique (cf. app/routers/dettes.py::valider_demande_credit) : les garants ne sont jamais des
utilisateurs KFSTORE, ils valident via un lien SMS à jeton unique. Partagé entre la demande
initiée depuis l'appli mobile (mon_credit.py) et celle créée par le staff pour un bénéficiaire
qui se présente en boutique (beneficiaires.py)."""
import logging
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db_models.models import BeneficiaireDB, DemandeCreditDB, DetteDB, EtablissementDB, ValidationGarantCreditDB
from app.models.schemas import StatutDemandeCredit, StatutDette, StatutValidationGarant, TiersType, TypeGarant
from app.services.audit import log_audit
from app.services.bareme_credit import plafond_disponible
from app.services.notifications import notifier_client
from app.services.sms import get_sms_provider

logger = logging.getLogger("kfstore.validation_garant")

DUREE_VALIDITE_JOURS = 7


def now_naive() -> datetime:
    """Les colonnes DateTime de la base ne portent pas de fuseau — par convention du projet,
    toute valeur qui y est écrite est en UTC ; on compare/stocke donc avec une valeur UTC
    dépouillée de son tzinfo, pour rester comparable à ce qui revient de la base (cf.
    app/routers/auth.py::_now_naive, même convention)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DemandeCreditBeneficiaireInput(BaseModel):
    boutique_id: str
    montant_souhaite: float
    motif: str


def creer_demande_credit_beneficiaire(
    db: Session, beneficiaire: BeneficiaireDB, payload: DemandeCreditBeneficiaireInput, cree_par: str,
) -> DemandeCreditDB:
    if not beneficiaire.client.credit_autorise:
        raise ValueError("L'engagement de remboursement signé doit être enregistré avant toute demande de crédit.")
    if beneficiaire.plafond_suspendu:
        raise ValueError("Le plafond de ce bénéficiaire est suspendu suite à un impayé non régularisé.")
    if payload.montant_souhaite <= 0:
        raise ValueError("Le montant doit être positif")
    disponible = plafond_disponible(db, beneficiaire)
    if payload.montant_souhaite > disponible:
        raise ValueError(f"Montant supérieur au plafond disponible ({disponible:,.0f} GNF)".replace(",", " "))

    demande = DemandeCreditDB(
        id=str(uuid.uuid4())[:8], client_id=beneficiaire.client_id, boutique_id=payload.boutique_id,
        montant_souhaite=payload.montant_souhaite, motif=payload.motif, statut=StatutDemandeCredit.en_attente,
        created_by=cree_par, updated_by=cree_par,
    )
    db.add(demande)
    db.flush()
    _creer_validations_garant(db, demande, beneficiaire, cree_par)
    return demande


def _creer_validations_garant(db: Session, demande: DemandeCreditDB, beneficiaire: BeneficiaireDB, auteur: str) -> None:
    etablissement = beneficiaire.etablissement
    expire_le = now_naive() + timedelta(days=DUREE_VALIDITE_JOURS)
    for type_garant, nom, contact in [
        (TypeGarant.referent, etablissement.referent_nom, etablissement.referent_contact),
        (TypeGarant.comptabilite, etablissement.comptabilite_nom, etablissement.comptabilite_contact),
    ]:
        token = secrets.token_urlsafe(24)
        db.add(ValidationGarantCreditDB(
            id=str(uuid.uuid4())[:8], demande_credit_id=demande.id, type_garant=type_garant,
            nom_garant=nom, contact_garant=contact, token=token, expire_le=expire_le,
            created_by=auteur, updated_by=auteur,
        ))
        montant = f"{demande.montant_souhaite:,.0f}".replace(",", " ")
        message = (
            f"KFSTORE — {beneficiaire.client.nom} ({etablissement.nom}) sollicite un crédit alimentaire de "
            f"{montant} GNF. Merci de valider ou refuser : https://admin.kfstore-gn.com/validation-garant/{token}"
        )
        if not get_sms_provider().send(contact, message):
            logger.warning("Échec envoi SMS validation garant (%s) à %s", type_garant.value, contact)


def appliquer_decision_garant(
    db: Session, v: ValidationGarantCreditDB, approuve: bool, motif_refus: str | None, auteur_label: str,
    updated_by: str | None = None, manuel: bool = False,
) -> None:
    """Enregistre la décision d'un garant (validation/refus) et, si les deux garants ont
    tranché, active ou refuse la demande de crédit — logique partagée entre la réponse du
    garant lui-même via son jeton SMS (validation_garant.py::repondre, public) et la saisie
    manuelle par un administrateur quand le SMS n'est jamais arrivé (route authentifiée
    /validation-garant/admin/{id}/decision, cf. SECOURS_SMS_GESTION). `auteur_label` alimente
    created_by/updated_by de la dette et le journal d'audit ; `updated_by`, s'il est fourni,
    est en plus posé sur la ligne de validation elle-même pour tracer qui a répondu à la
    place du garant. Verrouille la demande (SELECT ... FOR UPDATE) le temps de la décision :
    deux garants qui répondent au même instant, ou un double clic sur la validation manuelle
    pendant que l'envoi SMS traîne, ne doivent jamais aboutir à deux dettes pour une même
    demande — cf. incident constaté en production où une demande à 2 garants avait créé 2
    DetteDB de 500 000 GNF au lieu d'une seule."""
    demande = db.query(DemandeCreditDB).filter(DemandeCreditDB.id == v.demande_credit_id).with_for_update().one()
    db.refresh(v, with_for_update=True)

    if v.statut != StatutValidationGarant.en_attente:
        raise ValueError("Cette demande a déjà reçu une réponse pour ce garant")
    if not approuve and not motif_refus:
        raise ValueError("Un motif est requis en cas de refus")

    v.statut = StatutValidationGarant.validee if approuve else StatutValidationGarant.refusee
    v.date_reponse = now_naive()
    v.motif_refus = motif_refus if not approuve else None
    v.validee_manuellement = manuel
    if updated_by:
        v.updated_by = updated_by

    beneficiaire = db.query(BeneficiaireDB).filter(BeneficiaireDB.client_id == demande.client_id).first()
    toutes = db.query(ValidationGarantCreditDB).filter(ValidationGarantCreditDB.demande_credit_id == demande.id).all()

    if any(a.statut == StatutValidationGarant.refusee for a in toutes):
        demande.statut = StatutDemandeCredit.refusee
        demande.updated_by = auteur_label
        log_audit(db, f"Demande de crédit Aide Humanitaire refusée par un garant — {beneficiaire.client.nom}", auteur_label, demande.boutique_id)
        notifier_client(
            db, beneficiaire.client.nom,
            f"KFSTORE — Votre demande de crédit alimentaire de {demande.montant_souhaite:,.0f} GNF a été refusée "
            f"par un de vos garants.".replace(",", " "),
        )
    elif all(a.statut == StatutValidationGarant.validee for a in toutes):
        demande.statut = StatutDemandeCredit.validee
        demande.updated_by = auteur_label
        dette = DetteDB(
            id=str(uuid.uuid4())[:8], tiers_type=TiersType.client, tiers_nom=beneficiaire.client.nom, client_id=beneficiaire.client_id,
            boutique_id=demande.boutique_id, montant_initial=demande.montant_souhaite, solde_restant=demande.montant_souhaite,
            echeance=date.today() + timedelta(days=30), statut=StatutDette.en_cours, demande_credit_id=demande.id,
            created_by=auteur_label, updated_by=auteur_label,
        )
        db.add(dette)
        log_audit(db, f"Crédit Aide Humanitaire activé (2 garants validés) — {beneficiaire.client.nom} ({demande.montant_souhaite:,.0f} GNF)".replace(",", " "), auteur_label, demande.boutique_id)
        notifier_client(
            db, beneficiaire.client.nom,
            f"KFSTORE — Votre crédit alimentaire de {demande.montant_souhaite:,.0f} GNF est activé, vous pouvez "
            f"retirer vos denrées en boutique. Remboursement à échéance du {dette.echeance.strftime('%d/%m/%Y')}.".replace(",", " "),
        )
