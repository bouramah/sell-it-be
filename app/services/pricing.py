"""Résolution du prix d'un produit à une date donnée, à partir de périodes de validité.

Chaque (produit, boutique ou réseau, palier) a une suite de périodes [date_debut, date_fin]
sans chevauchement (contrôlé ici, cf. verifier_chevauchement — le backend est la seule source
de vérité, jamais confiance dans un calcul fait côté client). Une boutique_id NULL désigne le
prix de référence réseau ; une période boutique_id=X prévaut sur le réseau pour les dates
qu'elle couvre. C'est la seule source de vérité pour le prix : il n'y a plus de colonne "prix
actuel" — le prix du jour est simplement la période active à la date du jour, ce qui permet de
retrouver le prix catalogue applicable à la date de n'importe quelle vente passée (audit).
"""
from datetime import date

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db_models.models import PrixAchatDB, PrixPeriodeDB
from app.models.schemas import PalierPrix


def _periode_couvre(date_debut: date, date_fin: date | None, a_date: date) -> bool:
    return date_debut <= a_date and (date_fin is None or date_fin >= a_date)


def prix_effectif_a_date(db: Session, produit_id: str, boutique_id: str | None, palier: PalierPrix, a_date: date) -> float | None:
    """Prix applicable pour ce produit/palier à `a_date` : la surcharge boutique si elle couvre
    cette date, sinon le prix réseau. None si aucune période ne couvre cette date (produit sans
    prix défini à cette date, ex. avant sa création)."""
    if boutique_id:
        row = (
            db.query(PrixPeriodeDB)
            .filter(
                PrixPeriodeDB.produit_id == produit_id,
                PrixPeriodeDB.boutique_id == boutique_id,
                PrixPeriodeDB.palier == palier,
                PrixPeriodeDB.date_debut <= a_date,
                or_(PrixPeriodeDB.date_fin.is_(None), PrixPeriodeDB.date_fin >= a_date),
            )
            .first()
        )
        if row:
            return row.prix
    row = (
        db.query(PrixPeriodeDB)
        .filter(
            PrixPeriodeDB.produit_id == produit_id,
            PrixPeriodeDB.boutique_id.is_(None),
            PrixPeriodeDB.palier == palier,
            PrixPeriodeDB.date_debut <= a_date,
            or_(PrixPeriodeDB.date_fin.is_(None), PrixPeriodeDB.date_fin >= a_date),
        )
        .first()
    )
    return row.prix if row else None


def prix_effectifs_batch(
    db: Session, boutique_ids: set[str], produit_ids: set[str], a_date: date
) -> dict[tuple[str | None, str, PalierPrix], float]:
    """Comme prix_effectif_a_date mais pour beaucoup de (boutique, produit) à la fois (ex. GET
    /stock) — une seule requête. Clé (boutique_id ou None, produit_id, palier) ; pour un stock
    scopé à une boutique, croiser d'abord avec cette clé puis avec (None, produit_id, palier)."""
    if not produit_ids:
        return {}
    rows = (
        db.query(PrixPeriodeDB)
        .filter(
            PrixPeriodeDB.produit_id.in_(produit_ids),
            or_(PrixPeriodeDB.boutique_id.is_(None), PrixPeriodeDB.boutique_id.in_(boutique_ids)) if boutique_ids else PrixPeriodeDB.boutique_id.is_(None),
            PrixPeriodeDB.date_debut <= a_date,
            or_(PrixPeriodeDB.date_fin.is_(None), PrixPeriodeDB.date_fin >= a_date),
        )
        .all()
    )
    return {(r.boutique_id, r.produit_id, r.palier): r.prix for r in rows}


def resoudre_prix(cache: dict[tuple[str | None, str, PalierPrix], float], boutique_id: str, produit_id: str, palier: PalierPrix) -> float | None:
    """Lit le résultat de prix_effectifs_batch pour un (boutique, produit, palier) donné,
    surcharge boutique en priorité puis repli réseau."""
    if (boutique_id, produit_id, palier) in cache:
        return cache[(boutique_id, produit_id, palier)]
    return cache.get((None, produit_id, palier))


def verifier_chevauchement(
    db: Session,
    produit_id: str,
    boutique_id: str | None,
    palier: PalierPrix,
    date_debut: date,
    date_fin: date | None,
    exclure_id: str | None = None,
) -> PrixPeriodeDB | None:
    """Retourne la période existante en conflit avec [date_debut, date_fin] pour ce
    (produit, boutique, palier), ou None s'il n'y a pas de chevauchement."""
    query = db.query(PrixPeriodeDB).filter(
        PrixPeriodeDB.produit_id == produit_id,
        PrixPeriodeDB.boutique_id == boutique_id if boutique_id else PrixPeriodeDB.boutique_id.is_(None),
        PrixPeriodeDB.palier == palier,
    )
    if exclure_id:
        query = query.filter(PrixPeriodeDB.id != exclure_id)
    for existante in query.all():
        fin_existante = existante.date_fin or date.max
        fin_nouvelle = date_fin or date.max
        if date_debut <= fin_existante and existante.date_debut <= fin_nouvelle:
            return existante
    return None


# --- Prix d'achat (fournisseur) ------------------------------------------------------------
# Même principe que le prix de vente ci-dessus, mais toujours scopé à un fournisseur précis
# (un prix d'achat n'a pas d'équivalent "réseau" : chaque fournisseur fixe ses propres prix,
# éventuellement selon le volume acheté — cf. décision produit du 2026-08-14).


def prix_achat_effectif_a_date(db: Session, produit_id: str, fournisseur_id: str, palier: PalierPrix, a_date: date) -> float | None:
    row = (
        db.query(PrixAchatDB)
        .filter(
            PrixAchatDB.produit_id == produit_id,
            PrixAchatDB.fournisseur_id == fournisseur_id,
            PrixAchatDB.palier == palier,
            PrixAchatDB.date_debut <= a_date,
            or_(PrixAchatDB.date_fin.is_(None), PrixAchatDB.date_fin >= a_date),
        )
        .first()
    )
    return row.prix if row else None


def verifier_chevauchement_achat(
    db: Session,
    produit_id: str,
    fournisseur_id: str,
    palier: PalierPrix,
    date_debut: date,
    date_fin: date | None,
    exclure_id: str | None = None,
) -> PrixAchatDB | None:
    query = db.query(PrixAchatDB).filter(
        PrixAchatDB.produit_id == produit_id,
        PrixAchatDB.fournisseur_id == fournisseur_id,
        PrixAchatDB.palier == palier,
    )
    if exclure_id:
        query = query.filter(PrixAchatDB.id != exclure_id)
    for existante in query.all():
        fin_existante = existante.date_fin or date.max
        fin_nouvelle = date_fin or date.max
        if date_debut <= fin_existante and existante.date_debut <= fin_nouvelle:
            return existante
    return None
