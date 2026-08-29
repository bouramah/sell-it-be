"""Circuit de validation par les garants (référent + comptabilité de l'établissement) pour une
demande de crédit Aide Humanitaire — remplace la validation staff utilisée pour le crédit client
générique (cf. app/routers/dettes.py::valider_demande_credit) : les garants ne sont jamais des
utilisateurs KFSTORE, ils valident via un lien SMS à jeton unique. Partagé entre la demande
initiée depuis l'appli mobile (mon_credit.py) et celle créée par le staff pour un bénéficiaire
qui se présente en boutique (beneficiaires.py)."""
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db_models.models import BeneficiaireDB, DemandeCreditDB, EtablissementDB, ValidationGarantCreditDB
from app.models.schemas import StatutDemandeCredit, TypeGarant
from app.services.bareme_credit import plafond_disponible
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
