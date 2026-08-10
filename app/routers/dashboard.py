from datetime import date, timedelta

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends
from app.core.database import get_db
from app.db_models.models import (
    BoutiqueDB,
    CaisseDB,
    CommandeClientDB,
    CommandeFournisseurDB,
    DepenseDB,
    DetteDB,
    ProduitDB,
    StockBoutiqueDB,
    TransfertStockDB,
)
from app.models.schemas import StatutBoutique, StatutCaisse, StatutCommandeClient, StatutTransfert, TiersType

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


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
def get_dashboard(db: Session = Depends(get_db)) -> DashboardConsolide:
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
