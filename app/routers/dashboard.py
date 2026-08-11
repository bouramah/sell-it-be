from collections import defaultdict
from datetime import date, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends
from app.core.authorization import ROLES_PORTEE_RESEAU, a_portee_reseau, assert_boutique_access, boutiques_autorisees, require_role
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import (
    BoutiqueDB,
    CaisseDB,
    CommandeClientDB,
    CommandeFournisseurDB,
    DepenseDB,
    DetteDB,
    LigneCommandeClientDB,
    MouvementCaisseDB,
    MouvementStockDB,
    ProduitDB,
    StockBoutiqueDB,
    TransfertStockDB,
    UtilisateurDB,
)
from app.models.schemas import (
    CanalCommande,
    ModePaiement,
    StatutBoutique,
    StatutCaisse,
    StatutCommandeClient,
    StatutTransfert,
    TiersType,
    TypeMouvementCaisse,
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _boutique_scope(current_user: UtilisateurDB, boutique_id: str | None) -> list[str] | None:
    """Renvoie la liste des boutique_id à laquelle restreindre les requêtes du dashboard,
    ou None si aucune restriction n'est nécessaire (portée réseau, aucun filtre demandé)."""
    if boutique_id:
        assert_boutique_access(current_user, boutique_id)
        return [boutique_id]
    if a_portee_reseau(current_user):
        return None
    return list(boutiques_autorisees(current_user))


class LigneComparatifBoutique(BaseModel):
    boutique_id: str
    nom: str
    secteurs: list[str]
    ca_jour: float
    stock_en_alerte: int
    dettes_en_cours: float


class AlerteReseau(BaseModel):
    titre: str
    description: str


class LigneTopProduit(BaseModel):
    produit_id: str
    produit_nom: str
    secteur: str


class DashboardConsolide(BaseModel):
    chiffre_affaires_jour: float
    marge_nette_jour: float
    dettes_clients_en_cours: float
    produits_en_alerte_stock: int
    boutiques_concernees_alerte: int
    transferts_en_transit: int
    comparatif_boutiques: list[LigneComparatifBoutique]
    alertes: list[AlerteReseau]


@router.get("", response_model=DashboardConsolide)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> DashboardConsolide:
    # Dashboard consolidé réseau — réservé au siège (cf. CDC : "Consulter le dashboard consolidé siège").
    require_role(current_user, *ROLES_PORTEE_RESEAU)
    today = date.today()

    all_stock = db.query(StockBoutiqueDB).all()
    stock_alerte = [s for s in all_stock if s.quantite_disponible <= s.seuil_alerte]
    boutiques_avec_alerte = {s.boutique_id for s in stock_alerte}

    dettes_clients = db.query(DetteDB).filter(DetteDB.tiers_type == TiersType.client).all()
    total_dettes = sum(d.solde_restant for d in dettes_clients)

    transferts_en_transit = db.query(TransfertStockDB).filter(TransfertStockDB.statut == StatutTransfert.en_transit).count()

    commandes_clients = db.query(CommandeClientDB).filter(CommandeClientDB.statut != StatutCommandeClient.annulee).all()
    commandes_jour = [c for c in commandes_clients if c.date_creation.date() == today]

    commandes_fournisseurs_jour = db.query(CommandeFournisseurDB).filter(CommandeFournisseurDB.date_reception == today).all()
    depenses_jour = db.query(DepenseDB).filter(DepenseDB.date == today).all()

    ca_jour_total = sum(c.montant for c in commandes_jour)
    achats_jour_total = sum(c.montant for c in commandes_fournisseurs_jour)
    depenses_jour_total = sum(d.montant for d in depenses_jour)

    boutiques = db.query(BoutiqueDB).filter(BoutiqueDB.statut == StatutBoutique.active).all()
    comparatif = []
    for b in boutiques:
        stock_alerte_b = len([s for s in stock_alerte if s.boutique_id == b.id])
        dettes_b = sum(d.solde_restant for d in dettes_clients if d.boutique_id == b.id)
        ca_jour_b = sum(c.montant for c in commandes_jour if c.boutique_id == b.id)
        comparatif.append(
            LigneComparatifBoutique(
                boutique_id=b.id,
                nom=b.nom,
                secteurs=[s.secteur for s in b.secteurs],
                ca_jour=ca_jour_b,
                stock_en_alerte=stock_alerte_b,
                dettes_en_cours=dettes_b,
            )
        )

    alertes: list[AlerteReseau] = []

    produits_by_id = {p.id: p for p in db.query(ProduitDB).all()}
    stock_critique = sorted(
        [s for s in stock_alerte if s.seuil_alerte > 0],
        key=lambda s: s.quantite_disponible - s.seuil_alerte,
    )
    if stock_critique:
        s = stock_critique[0]
        nom = produits_by_id[s.produit_id].nom if s.produit_id in produits_by_id else s.produit_id
        alertes.append(AlerteReseau(
            titre="Rupture de stock imminente",
            description=f"{nom} — {s.boutique_id}, {s.quantite_disponible} unité(s) restante(s)",
        ))

    caisses_ecart = db.query(CaisseDB).filter(CaisseDB.statut == StatutCaisse.ecart_signale).all()
    for c in caisses_ecart[:1]:
        ecart = abs(c.solde_reel - c.solde_theorique)
        alertes.append(AlerteReseau(
            titre="Écart de caisse non justifié",
            description=f"Caisse {c.libelle} — {c.boutique_id}, écart de {ecart:,.0f} GNF".replace(",", " "),
        ))

    if transferts_en_transit:
        alertes.append(AlerteReseau(
            titre="Transferts en cours de route",
            description=f"{transferts_en_transit} transfert(s) de stock actuellement en transit",
        ))

    echeance_proche = [
        d for d in dettes_clients
        if d.solde_restant > 0 and d.echeance <= today + timedelta(days=2)
    ]
    if echeance_proche:
        alertes.append(AlerteReseau(
            titre="Dette proche échéance",
            description=f"{len(echeance_proche)} client(s) approchent ou dépassent l'échéance sous 48h",
        ))

    return DashboardConsolide(
        chiffre_affaires_jour=ca_jour_total,
        marge_nette_jour=ca_jour_total - achats_jour_total - depenses_jour_total,
        dettes_clients_en_cours=total_dettes,
        produits_en_alerte_stock=len(stock_alerte),
        boutiques_concernees_alerte=len(boutiques_avec_alerte),
        transferts_en_transit=transferts_en_transit,
        comparatif_boutiques=comparatif,
        alertes=alertes,
    )


class KpiCanal(BaseModel):
    canal: CanalCommande
    montant: float
    nombre: int


class KpiModePaiement(BaseModel):
    mode: ModePaiement
    montant: float


class KpiTopProduit(BaseModel):
    produit_id: str
    produit_nom: str
    quantite: int
    montant: float


class KpiTopBoutique(BaseModel):
    boutique_id: str
    nom: str
    montant: float


class KpiVentes(BaseModel):
    chiffre_affaires: float
    nombre_commandes: int
    panier_moyen: float
    par_canal: list[KpiCanal]
    par_mode_paiement: list[KpiModePaiement]
    top_produits: list[KpiTopProduit]
    top_boutiques: list[KpiTopBoutique]


class KpiCaisse(BaseModel):
    encaissements: float
    decaissements: float
    flux_net: float


class KpiStock(BaseModel):
    entrees: int
    sorties: int


class KpiFinance(BaseModel):
    depenses: float
    marge_nette: float
    dettes_clients_en_cours: float


class BoutiqueCarte(BaseModel):
    boutique_id: str
    nom: str
    latitude: float | None
    longitude: float | None
    ca_periode: float
    alertes_stock: int


class DashboardKpis(BaseModel):
    debut: datetime
    fin: datetime
    ventes: KpiVentes
    caisse: KpiCaisse
    stock: KpiStock
    finance: KpiFinance
    boutiques: list[BoutiqueCarte]


@router.get("/kpis", response_model=DashboardKpis)
def get_dashboard_kpis(
    debut: datetime,
    fin: datetime,
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> DashboardKpis:
    scope = _boutique_scope(current_user, boutique_id)
    debut_date, fin_date = debut.date(), fin.date()

    commandes_q = db.query(CommandeClientDB).filter(
        CommandeClientDB.statut != StatutCommandeClient.annulee,
        CommandeClientDB.date_creation >= debut,
        CommandeClientDB.date_creation <= fin,
    )
    if scope is not None:
        commandes_q = commandes_q.filter(CommandeClientDB.boutique_id.in_(scope))
    commandes = commandes_q.all()

    chiffre_affaires = sum(c.montant for c in commandes)
    nombre_commandes = len(commandes)
    panier_moyen = chiffre_affaires / nombre_commandes if nombre_commandes else 0.0

    par_canal: dict[CanalCommande, list[float]] = defaultdict(lambda: [0.0, 0])
    par_mode: dict[ModePaiement, float] = defaultdict(float)
    boutiques_montant: dict[str, float] = defaultdict(float)
    for c in commandes:
        par_canal[c.canal][0] += c.montant
        par_canal[c.canal][1] += 1
        par_mode[c.mode_paiement] += c.montant
        boutiques_montant[c.boutique_id] += c.montant

    commande_ids = [c.id for c in commandes]
    top_produits: list[KpiTopProduit] = []
    if commande_ids:
        lignes = db.query(LigneCommandeClientDB).filter(LigneCommandeClientDB.commande_id.in_(commande_ids)).all()
        produits_by_id = {p.id: p for p in db.query(ProduitDB).all()}
        agg: dict[str, list[float]] = defaultdict(lambda: [0, 0.0])
        for l in lignes:
            agg[l.produit_id][0] += l.quantite
            agg[l.produit_id][1] += l.quantite * l.prix_unitaire
        top_produits = sorted(
            [
                KpiTopProduit(
                    produit_id=pid,
                    produit_nom=produits_by_id[pid].nom if pid in produits_by_id else pid,
                    quantite=int(vals[0]),
                    montant=vals[1],
                )
                for pid, vals in agg.items()
            ],
            key=lambda t: t.montant,
            reverse=True,
        )[:5]

    boutiques_by_id = {b.id: b for b in db.query(BoutiqueDB).all()}
    top_boutiques = sorted(
        [
            KpiTopBoutique(boutique_id=bid, nom=boutiques_by_id[bid].nom if bid in boutiques_by_id else bid, montant=montant)
            for bid, montant in boutiques_montant.items()
        ],
        key=lambda t: t.montant,
        reverse=True,
    )[:5]

    ventes = KpiVentes(
        chiffre_affaires=chiffre_affaires,
        nombre_commandes=nombre_commandes,
        panier_moyen=panier_moyen,
        par_canal=[KpiCanal(canal=canal, montant=vals[0], nombre=int(vals[1])) for canal, vals in par_canal.items()],
        par_mode_paiement=[KpiModePaiement(mode=mode, montant=montant) for mode, montant in par_mode.items()],
        top_produits=top_produits,
        top_boutiques=top_boutiques,
    )

    mouvements_caisse_q = db.query(MouvementCaisseDB).filter(
        MouvementCaisseDB.horodatage >= debut,
        MouvementCaisseDB.horodatage <= fin,
    )
    if scope is not None:
        mouvements_caisse_q = mouvements_caisse_q.filter(MouvementCaisseDB.boutique_id.in_(scope))
    mouvements_caisse = mouvements_caisse_q.all()
    encaissements = sum(m.montant for m in mouvements_caisse if m.type == TypeMouvementCaisse.encaissement)
    decaissements = sum(-m.montant for m in mouvements_caisse if m.type == TypeMouvementCaisse.decaissement)
    caisse = KpiCaisse(encaissements=encaissements, decaissements=decaissements, flux_net=encaissements - decaissements)

    mouvements_stock_q = db.query(MouvementStockDB).filter(
        MouvementStockDB.horodatage >= debut,
        MouvementStockDB.horodatage <= fin,
    )
    if scope is not None:
        mouvements_stock_q = mouvements_stock_q.filter(MouvementStockDB.boutique_id.in_(scope))
    mouvements_stock = mouvements_stock_q.all()
    entrees = sum(m.quantite for m in mouvements_stock if m.quantite > 0)
    sorties = sum(-m.quantite for m in mouvements_stock if m.quantite < 0)
    stock = KpiStock(entrees=entrees, sorties=sorties)

    depenses_q = db.query(DepenseDB).filter(DepenseDB.date >= debut_date, DepenseDB.date <= fin_date)
    if scope is not None:
        depenses_q = depenses_q.filter(DepenseDB.boutique_id.in_(scope))
    depenses_total = sum(d.montant for d in depenses_q.all())

    achats_q = db.query(CommandeFournisseurDB).filter(
        CommandeFournisseurDB.date_reception.isnot(None),
        CommandeFournisseurDB.date_reception >= debut_date,
        CommandeFournisseurDB.date_reception <= fin_date,
    )
    if scope is not None:
        achats_q = achats_q.filter(CommandeFournisseurDB.boutique_id.in_(scope))
    achats_total = sum(c.montant for c in achats_q.all())

    dettes_q = db.query(DetteDB).filter(DetteDB.tiers_type == TiersType.client)
    if scope is not None:
        dettes_q = dettes_q.filter(DetteDB.boutique_id.in_(scope))
    dettes_clients_en_cours = sum(d.solde_restant for d in dettes_q.all())

    finance = KpiFinance(
        depenses=depenses_total,
        marge_nette=chiffre_affaires - achats_total - depenses_total,
        dettes_clients_en_cours=dettes_clients_en_cours,
    )

    all_stock = db.query(StockBoutiqueDB).all()
    stock_alerte_par_boutique: dict[str, int] = defaultdict(int)
    for s in all_stock:
        if s.quantite_disponible <= s.seuil_alerte:
            stock_alerte_par_boutique[s.boutique_id] += 1

    boutiques_carte = [
        BoutiqueCarte(
            boutique_id=b.id,
            nom=b.nom,
            latitude=b.latitude,
            longitude=b.longitude,
            ca_periode=boutiques_montant.get(b.id, 0.0),
            alertes_stock=stock_alerte_par_boutique.get(b.id, 0),
        )
        for b in db.query(BoutiqueDB).filter(BoutiqueDB.statut == StatutBoutique.active).all()
        if scope is None or b.id in scope
    ]

    return DashboardKpis(
        debut=debut,
        fin=fin,
        ventes=ventes,
        caisse=caisse,
        stock=stock,
        finance=finance,
        boutiques=boutiques_carte,
    )
