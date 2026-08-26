from datetime import date, datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from app.core.authorization import a_portee_reseau, apply_boutique_filter, boutiques_autorisees, require_permission
from app.core.database import get_db
from app.core.module_actions import COMPTABILITE_BOUTIQUE, COMPTABILITE_RESEAU
from app.core.security import get_current_user
from app.db_models.models import (
    BoutiqueDB,
    CommandeClientDB,
    CommandeFournisseurDB,
    DepenseDB,
    DetteDB,
    LigneCommandeClientDB,
    PrixAchatDB,
    ProduitDB,
    RemboursementDB,
    StockBoutiqueDB,
    UtilisateurDB,
)
from app.models.schemas import (
    CompteResultatBoutique,
    EcritureComptable,
    EtatStockValorise,
    LigneMargeProduit,
    LigneStockValorise,
    MargeProduits,
    PalierPrix,
    StatutCommandeClient,
    StatutCommandeFournisseur,
)
from app.services.excel import export_comptabilite_xlsx

router = APIRouter(prefix="/api/v1/comptabilite", tags=["comptabilite"])


class ComptabiliteConsolidee(BaseModel):
    ca_consolide: float
    marge_nette_consolidee: float
    depenses_consolidees: float
    marge_nette_moyenne_pct: float
    comptes: list[CompteResultatBoutique]


def _calculer_comptes(db: Session, current_user: UtilisateurDB) -> ComptabiliteConsolidee:
    boutiques_q = db.query(BoutiqueDB)
    if not a_portee_reseau(current_user):
        boutiques_q = boutiques_q.filter(BoutiqueDB.id.in_(boutiques_autorisees(current_user)))
    boutiques = boutiques_q.all()

    commandes_clients = db.query(CommandeClientDB).filter(CommandeClientDB.statut != StatutCommandeClient.annulee).all()
    commandes_fournisseurs = db.query(CommandeFournisseurDB).filter(
        CommandeFournisseurDB.statut.in_([StatutCommandeFournisseur.receptionnee, StatutCommandeFournisseur.cloturee])
    ).all()
    depenses = db.query(DepenseDB).all()

    comptes = []
    for b in boutiques:
        ca = sum(c.montant for c in commandes_clients if c.boutique_id == b.id)
        achats = sum(c.montant for c in commandes_fournisseurs if c.boutique_id == b.id)
        dep = sum(d.montant for d in depenses if d.boutique_id == b.id)
        comptes.append(CompteResultatBoutique(
            boutique_id=b.id, chiffre_affaires=ca, achats=achats, depenses=dep, marge_nette=ca - achats - dep,
        ))

    ca_total = sum(c.chiffre_affaires for c in comptes)
    marge_total = sum(c.marge_nette for c in comptes)
    depenses_total = sum(c.depenses for c in comptes)

    return ComptabiliteConsolidee(
        ca_consolide=ca_total,
        marge_nette_consolidee=marge_total,
        depenses_consolidees=depenses_total,
        marge_nette_moyenne_pct=round((marge_total / ca_total) * 100, 1) if ca_total else 0,
        comptes=comptes,
    )


@router.get("", response_model=ComptabiliteConsolidee)
def get_comptabilite(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ComptabiliteConsolidee:
    # L'accès à la route est autorisé si l'une des deux lignes ("de sa boutique" ou
    # "consolidée du réseau") accorde un droit — le scope réel (une boutique ou tout le
    # réseau) est ensuite déterminé par a_portee_reseau() ci-dessous.
    require_permission(db, current_user, COMPTABILITE_BOUTIQUE, COMPTABILITE_RESEAU)
    return _calculer_comptes(db, current_user)


def _calculer_journal(db: Session, current_user: UtilisateurDB, boutique_id: str | None) -> list[EcritureComptable]:
    ventes = apply_boutique_filter(
        db.query(CommandeClientDB).filter(CommandeClientDB.statut != StatutCommandeClient.annulee),
        CommandeClientDB.boutique_id, current_user, boutique_id,
    ).all()
    achats = apply_boutique_filter(
        db.query(CommandeFournisseurDB).filter(
            CommandeFournisseurDB.statut.in_([StatutCommandeFournisseur.receptionnee, StatutCommandeFournisseur.cloturee])
        ),
        CommandeFournisseurDB.boutique_id, current_user, boutique_id,
    ).all()
    depenses = apply_boutique_filter(db.query(DepenseDB), DepenseDB.boutique_id, current_user, boutique_id).all()
    remboursements = (
        apply_boutique_filter(db.query(RemboursementDB).join(DetteDB), DetteDB.boutique_id, current_user, boutique_id)
        .all()
    )

    ecritures = [
        EcritureComptable(
            id=c.id, date=c.created_at.isoformat() if c.created_at else "", boutique_id=c.boutique_id,
            nature="vente", sens="credit", montant=c.montant, libelle=f"Vente — commande #{c.id} ({c.client_nom})",
            auteur=c.created_by, operation_source_type="commande_client", operation_source_id=c.id,
        )
        for c in ventes
    ] + [
        EcritureComptable(
            id=c.id, date=c.created_at.isoformat() if c.created_at else "", boutique_id=c.boutique_id,
            nature="achat", sens="debit", montant=c.montant, libelle=f"Achat fournisseur — commande #{c.id}",
            auteur=c.created_by, operation_source_type="commande_fournisseur", operation_source_id=c.id,
        )
        for c in achats
    ] + [
        EcritureComptable(
            id=d.id, date=d.date.isoformat(), boutique_id=d.boutique_id,
            nature="depense", sens="debit", montant=d.montant, libelle=f"Dépense — {d.categorie} ({d.auteur})",
            auteur=d.created_by, operation_source_type="depense", operation_source_id=d.id,
        )
        for d in depenses
    ] + [
        EcritureComptable(
            id=r.id, date=r.date.isoformat(), boutique_id=r.dette.boutique_id,
            nature="remboursement", sens="credit", montant=r.montant, libelle=f"Remboursement de créance — {r.dette.tiers_nom}",
            auteur=r.created_by, operation_source_type="remboursement", operation_source_id=r.id,
        )
        for r in remboursements
    ]
    return sorted(ecritures, key=lambda e: e.date, reverse=True)


@router.get("/journal", response_model=list[EcritureComptable])
def journal_comptable(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[EcritureComptable]:
    """Journal des opérations (CDC §3.14) : dérivé sans double saisie des ventes, achats,
    dépenses et remboursements déjà enregistrés dans les autres modules — jamais une saisie
    comptable manuelle indépendante, pour garantir la cohérence avec l'activité opérationnelle."""
    require_permission(db, current_user, COMPTABILITE_BOUTIQUE, COMPTABILITE_RESEAU)
    return _calculer_journal(db, current_user, boutique_id)


def _calculer_stock_valorise(db: Session, current_user: UtilisateurDB, boutique_id: str | None) -> EtatStockValorise:
    lignes_stock = apply_boutique_filter(
        db.query(StockBoutiqueDB), StockBoutiqueDB.boutique_id, current_user, boutique_id
    ).all()
    produit_ids = {l.produit_id for l in lignes_stock}
    if not produit_ids:
        return EtatStockValorise(lignes=[], valeur_totale=0)

    produits_by_id = {p.id: p for p in db.query(ProduitDB).filter(ProduitDB.id.in_(produit_ids)).all()}
    today = date.today()
    prix_achats = (
        db.query(PrixAchatDB)
        .filter(
            PrixAchatDB.produit_id.in_(produit_ids), PrixAchatDB.palier == PalierPrix.detail,
            PrixAchatDB.date_debut <= today,
        )
        .all()
    )
    couts_par_produit: dict[str, list[float]] = {}
    for pa in prix_achats:
        if pa.date_fin is not None and pa.date_fin < today:
            continue
        couts_par_produit.setdefault(pa.produit_id, []).append(pa.prix)

    lignes = []
    for l in lignes_stock:
        produit = produits_by_id.get(l.produit_id)
        if not produit:
            continue
        couts = couts_par_produit.get(l.produit_id)
        cout_moyen = sum(couts) / len(couts) if couts else None
        lignes.append(LigneStockValorise(
            boutique_id=l.boutique_id, produit_id=l.produit_id, produit_nom=produit.nom,
            quantite=l.quantite_disponible, cout_unitaire_moyen=cout_moyen,
            valeur=(cout_moyen or 0) * l.quantite_disponible,
        ))

    return EtatStockValorise(lignes=lignes, valeur_totale=sum(l.valeur for l in lignes))


@router.get("/stock-valorise", response_model=EtatStockValorise)
def etat_stock_valorise(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> EtatStockValorise:
    """État des stocks valorisés (CDC §3.14) : chaque ligne de stock valorisée au coût moyen
    d'achat (moyenne des prix d'achat fournisseurs actifs à ce jour, palier détail) — un
    produit sans prix d'achat renseigné apparaît avec un coût nul (non valorisable), plutôt
    que d'inventer une valeur, pour ne jamais surestimer la valeur du stock."""
    require_permission(db, current_user, COMPTABILITE_BOUTIQUE, COMPTABILITE_RESEAU)
    return _calculer_stock_valorise(db, current_user, boutique_id)


def _calculer_marge_produits(
    db: Session, current_user: UtilisateurDB, debut: datetime, fin: datetime,
    boutique_id: str | None, produit_id: str | None,
) -> MargeProduits:
    """Bénéfice par produit sur une période libre — coût unitaire résolu au même titre que
    l'état des stocks valorisés (moyenne des prix d'achat fournisseurs actifs à la date de la
    vente, pour le palier réellement vendu) : un produit sans prix d'achat renseigné n'est pas
    valorisable, sa marge apparaît à None plutôt que d'inventer un coût."""
    commandes_q = apply_boutique_filter(
        db.query(CommandeClientDB).filter(
            CommandeClientDB.statut != StatutCommandeClient.annulee,
            CommandeClientDB.date_creation >= debut,
            CommandeClientDB.date_creation <= fin,
        ),
        CommandeClientDB.boutique_id, current_user, boutique_id,
    )
    commandes = commandes_q.all()
    if not commandes:
        return MargeProduits(date_debut=debut, date_fin=fin, boutique_id=boutique_id, chiffre_affaires_total=0, marge_totale=0, lignes=[])

    date_vente_par_commande = {c.id: c.date_creation.date() for c in commandes}
    commande_ids = list(date_vente_par_commande.keys())

    lignes_q = db.query(LigneCommandeClientDB).filter(LigneCommandeClientDB.commande_id.in_(commande_ids))
    if produit_id:
        lignes_q = lignes_q.filter(LigneCommandeClientDB.produit_id == produit_id)
    lignes = lignes_q.all()

    produit_ids = {l.produit_id for l in lignes}
    produits_by_id = {p.id: p for p in db.query(ProduitDB).filter(ProduitDB.id.in_(produit_ids)).all()} if produit_ids else {}
    prix_achats = db.query(PrixAchatDB).filter(PrixAchatDB.produit_id.in_(produit_ids)).all() if produit_ids else []

    def cout_unitaire(pid: str, palier: PalierPrix, a_date: date) -> float | None:
        couts = [
            pa.prix for pa in prix_achats
            if pa.produit_id == pid and pa.palier == palier
            and pa.date_debut <= a_date and (pa.date_fin is None or pa.date_fin >= a_date)
        ]
        return sum(couts) / len(couts) if couts else None

    agrege: dict[str, dict] = {}
    for l in lignes:
        entry = agrege.setdefault(l.produit_id, {"quantite": 0, "ca": 0.0, "cout": 0.0, "cout_connu": True})
        entry["quantite"] += l.quantite
        entry["ca"] += l.quantite * l.prix_unitaire
        cout = cout_unitaire(l.produit_id, l.palier, date_vente_par_commande[l.commande_id])
        if cout is None:
            entry["cout_connu"] = False
        else:
            entry["cout"] += l.quantite * cout

    resultat_lignes = [
        LigneMargeProduit(
            produit_id=pid, produit_nom=produits_by_id[pid].nom if pid in produits_by_id else pid,
            quantite_vendue=entry["quantite"], chiffre_affaires=entry["ca"],
            cout_total=entry["cout"] if entry["cout_connu"] else None,
            marge=(entry["ca"] - entry["cout"]) if entry["cout_connu"] else None,
            marge_pct=round((entry["ca"] - entry["cout"]) / entry["ca"] * 100, 1) if entry["cout_connu"] and entry["ca"] else None,
        )
        for pid, entry in sorted(agrege.items(), key=lambda kv: kv[1]["ca"], reverse=True)
    ]
    ca_total = sum(l.chiffre_affaires for l in resultat_lignes)
    marge_connue = [l.marge for l in resultat_lignes if l.marge is not None]
    marge_totale = sum(marge_connue) if marge_connue else None

    return MargeProduits(
        date_debut=debut, date_fin=fin, boutique_id=boutique_id,
        chiffre_affaires_total=ca_total, marge_totale=marge_totale, lignes=resultat_lignes,
    )


@router.get("/marge-produits", response_model=MargeProduits)
def marge_produits(
    debut: datetime,
    fin: datetime,
    boutique_id: str | None = None,
    produit_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> MargeProduits:
    require_permission(db, current_user, COMPTABILITE_BOUTIQUE, COMPTABILITE_RESEAU)
    return _calculer_marge_produits(db, current_user, debut, fin, boutique_id, produit_id)


@router.get("/export.xlsx")
def exporter_comptabilite_xlsx(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Response:
    """Export réellement au format Excel (.xlsx, via openpyxl) — pas un CSV renommé — avec
    trois feuilles : compte de résultat, journal des opérations, stock valorisé (CDC §3.14)."""
    require_permission(db, current_user, COMPTABILITE_BOUTIQUE, COMPTABILITE_RESEAU)
    comptes = _calculer_comptes(db, current_user).comptes
    ecritures = _calculer_journal(db, current_user, boutique_id)
    stock = _calculer_stock_valorise(db, current_user, boutique_id).lignes
    noms_boutiques = {b.id: b.nom for b in db.query(BoutiqueDB).all()}

    contenu = export_comptabilite_xlsx(comptes, ecritures, stock, noms_boutiques)
    return Response(
        content=contenu,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=comptabilite-kfstore.xlsx"},
    )
