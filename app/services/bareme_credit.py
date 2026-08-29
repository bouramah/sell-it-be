"""Résolution du plafond de crédit Aide Humanitaire à une date donnée, à partir de périodes de
validité — même principe que app/services/pricing.py (prix par période) : une ligne
etablissement_id=None fait référence réseau ; une ligne etablissement_id=X la surcharge pour cet
établissement si elle couvre la date. Le backend reste la seule source de vérité, jamais confiance
dans un calcul fait côté client."""
import uuid
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db_models.models import BaremeCreditBeneficiaireDB, BeneficiaireDB, DetteDB, RemboursementDB
from app.models.schemas import ModePaiement, StatutDette


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


def regler_dette_beneficiaire(
    db: Session, dette: DetteDB, montant: float, mode_paiement: ModePaiement, date_paiement: date, operateur: str,
    auteur: str, caisse_id: str | None = None, versement_etablissement_id: str | None = None,
) -> RemboursementDB:
    """Solde (totalement ou partiellement) une dette de bénéficiaire et lève la suspension du
    plafond si plus aucune autre dette de ce client n'est en retard — logique partagée entre
    l'encaissement en boutique (dettes.py, avec mouvement de caisse) et le rapprochement d'un
    versement groupé d'établissement (aide_humanitaire.py, sans caisse : l'argent arrive par
    virement au siège, pas dans une caisse boutique). `operateur` est la personne qui a
    physiquement traité le paiement (saisie libre) ; `auteur` est l'utilisateur KFSTORE
    authentifié qui enregistre l'opération (audit created_by/updated_by) — pas nécessairement
    la même personne."""
    r = RemboursementDB(
        id=str(uuid.uuid4())[:8], dette_id=dette.id, caisse_id=caisse_id, montant=montant,
        mode_paiement=mode_paiement, date=date_paiement, operateur=operateur,
        versement_etablissement_id=versement_etablissement_id,
        created_by=auteur, updated_by=auteur,
    )
    db.add(r)

    dette.solde_restant -= montant
    dette.statut = StatutDette.soldee if dette.solde_restant <= 0 else StatutDette.en_cours
    dette.updated_by = auteur

    if dette.statut == StatutDette.soldee and dette.client_id:
        beneficiaire = db.query(BeneficiaireDB).filter(BeneficiaireDB.client_id == dette.client_id).first()
        if beneficiaire and beneficiaire.plafond_suspendu:
            autres_en_retard = db.query(DetteDB).filter(
                DetteDB.client_id == dette.client_id, DetteDB.id != dette.id, DetteDB.statut == StatutDette.en_retard,
            ).first()
            if not autres_en_retard:
                beneficiaire.plafond_suspendu = False
                beneficiaire.updated_by = auteur

    return r
