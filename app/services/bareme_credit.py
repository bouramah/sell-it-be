"""Résolution du plafond de crédit enseignant à une date donnée, à partir de périodes de
validité — même principe que app/services/pricing.py (prix par période) : une ligne
ecole_id=None fait référence réseau ; une ligne ecole_id=X la surcharge pour cette école si
elle couvre la date. Le backend reste la seule source de vérité, jamais confiance dans un
calcul fait côté client."""
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db_models.models import BaremeCreditEnseignantDB, DetteDB, EnseignantDB
from app.models.schemas import StatutDette


def plafond_effectif_a_date(db: Session, ecole_id: str, grade_echelon: str, a_date: date) -> float | None:
    """Plafond applicable pour ce grade/échelon à `a_date` : la surcharge école si elle couvre
    cette date, sinon le barème réseau. None si aucune période ne couvre cette date."""
    row = (
        db.query(BaremeCreditEnseignantDB)
        .filter(
            BaremeCreditEnseignantDB.ecole_id == ecole_id,
            BaremeCreditEnseignantDB.grade_echelon == grade_echelon,
            BaremeCreditEnseignantDB.date_debut <= a_date,
            or_(BaremeCreditEnseignantDB.date_fin.is_(None), BaremeCreditEnseignantDB.date_fin >= a_date),
        )
        .first()
    )
    if row:
        return row.plafond
    row = (
        db.query(BaremeCreditEnseignantDB)
        .filter(
            BaremeCreditEnseignantDB.ecole_id.is_(None),
            BaremeCreditEnseignantDB.grade_echelon == grade_echelon,
            BaremeCreditEnseignantDB.date_debut <= a_date,
            or_(BaremeCreditEnseignantDB.date_fin.is_(None), BaremeCreditEnseignantDB.date_fin >= a_date),
        )
        .first()
    )
    return row.plafond if row else None


def verifier_chevauchement_bareme(
    db: Session,
    ecole_id: str | None,
    grade_echelon: str,
    date_debut: date,
    date_fin: date | None,
    exclure_id: str | None = None,
) -> BaremeCreditEnseignantDB | None:
    """Retourne la période existante en conflit avec [date_debut, date_fin] pour ce
    (ecole_id, grade_echelon), ou None s'il n'y a pas de chevauchement."""
    query = db.query(BaremeCreditEnseignantDB).filter(
        BaremeCreditEnseignantDB.ecole_id == ecole_id if ecole_id else BaremeCreditEnseignantDB.ecole_id.is_(None),
        BaremeCreditEnseignantDB.grade_echelon == grade_echelon,
    )
    if exclure_id:
        query = query.filter(BaremeCreditEnseignantDB.id != exclure_id)
    for existante in query.all():
        fin_existante = existante.date_fin or date.max
        fin_nouvelle = date_fin or date.max
        if date_debut <= fin_existante and existante.date_debut <= fin_nouvelle:
            return existante
    return None


def plafond_disponible(db: Session, enseignant: EnseignantDB, a_date: date | None = None) -> float:
    """Plafond effectif moins l'encours de dette de ce client (dettes non soldées) — 0 si le
    plafond est suspendu (impayé non régularisé, CDC §4.6). C'est le point de contrôle unique
    utilisé à la fois pour la vente à crédit en boutique et pour l'activation d'une demande."""
    if enseignant.plafond_suspendu:
        return 0.0
    plafond = plafond_effectif_a_date(db, enseignant.ecole_id, enseignant.grade_echelon, a_date or date.today())
    if plafond is None:
        return 0.0
    encours = (
        db.query(DetteDB)
        .filter(DetteDB.client_id == enseignant.client_id, DetteDB.statut != StatutDette.soldee)
        .all()
    )
    engage = sum(d.solde_restant for d in encours)
    return max(0.0, plafond - engage)
