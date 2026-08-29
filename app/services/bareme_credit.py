"""Résolution du plafond de crédit Aide Humanitaire à une date donnée, à partir de périodes de
validité — même principe que app/services/pricing.py (prix par période) : une ligne
etablissement_id=None fait référence réseau ; une ligne etablissement_id=X la surcharge pour cet
établissement si elle couvre la date. Le backend reste la seule source de vérité, jamais confiance
dans un calcul fait côté client."""
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db_models.models import BaremeCreditBeneficiaireDB, BeneficiaireDB, DetteDB
from app.models.schemas import StatutDette


def plafond_effectif_a_date(db: Session, etablissement_id: str, poste: str, a_date: date) -> float | None:
    """Plafond applicable pour ce poste à `a_date` : la surcharge établissement si elle couvre
    cette date, sinon le barème réseau. None si aucune période ne couvre cette date."""
    row = (
        db.query(BaremeCreditBeneficiaireDB)
        .filter(
            BaremeCreditBeneficiaireDB.etablissement_id == etablissement_id,
            BaremeCreditBeneficiaireDB.poste == poste,
            BaremeCreditBeneficiaireDB.date_debut <= a_date,
            or_(BaremeCreditBeneficiaireDB.date_fin.is_(None), BaremeCreditBeneficiaireDB.date_fin >= a_date),
        )
        .first()
    )
    if row:
        return row.plafond
    row = (
        db.query(BaremeCreditBeneficiaireDB)
        .filter(
            BaremeCreditBeneficiaireDB.etablissement_id.is_(None),
            BaremeCreditBeneficiaireDB.poste == poste,
            BaremeCreditBeneficiaireDB.date_debut <= a_date,
            or_(BaremeCreditBeneficiaireDB.date_fin.is_(None), BaremeCreditBeneficiaireDB.date_fin >= a_date),
        )
        .first()
    )
    return row.plafond if row else None


def verifier_chevauchement_bareme(
    db: Session,
    etablissement_id: str | None,
    poste: str,
    date_debut: date,
    date_fin: date | None,
    exclure_id: str | None = None,
) -> BaremeCreditBeneficiaireDB | None:
    """Retourne la période existante en conflit avec [date_debut, date_fin] pour ce
    (etablissement_id, poste), ou None s'il n'y a pas de chevauchement."""
    query = db.query(BaremeCreditBeneficiaireDB).filter(
        BaremeCreditBeneficiaireDB.etablissement_id == etablissement_id if etablissement_id else BaremeCreditBeneficiaireDB.etablissement_id.is_(None),
        BaremeCreditBeneficiaireDB.poste == poste,
    )
    if exclure_id:
        query = query.filter(BaremeCreditBeneficiaireDB.id != exclure_id)
    for existante in query.all():
        fin_existante = existante.date_fin or date.max
        fin_nouvelle = date_fin or date.max
        if date_debut <= fin_existante and existante.date_debut <= fin_nouvelle:
            return existante
    return None


def plafond_disponible(db: Session, beneficiaire: BeneficiaireDB, a_date: date | None = None) -> float:
    """Plafond effectif moins l'encours de dette de ce client (dettes non soldées) — 0 si le
    plafond est suspendu (impayé non régularisé). C'est le point de contrôle unique utilisé à la
    fois pour la vente à crédit en boutique et pour l'activation d'une demande."""
    if beneficiaire.plafond_suspendu:
        return 0.0
    plafond = plafond_effectif_a_date(db, beneficiaire.etablissement_id, beneficiaire.poste, a_date or date.today())
    if plafond is None:
        return 0.0
    encours = (
        db.query(DetteDB)
        .filter(DetteDB.client_id == beneficiaire.client_id, DetteDB.statut != StatutDette.soldee)
        .all()
    )
    engage = sum(d.solde_restant for d in encours)
    return max(0.0, plafond - engage)
