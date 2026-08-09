from pydantic import BaseModel

from fastapi import APIRouter
from app.data.fixtures import BOUTIQUES, CA_JOUR, DETTES, PRODUITS, STOCKS
from app.models.schemas import StatutBoutique, TiersType

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
def get_dashboard() -> DashboardConsolide:
    produits_by_id = {p.id: p for p in PRODUITS}

    stock_alerte = [s for s in STOCKS if s.quantite_disponible <= s.seuil_alerte]
    boutiques_avec_alerte = {s.boutique_id for s in stock_alerte}

    dettes_clients = [d for d in DETTES if d.tiers_type == TiersType.client]
    total_dettes = sum(d.solde_restant for d in dettes_clients)

    comparatif = []
    for b in BOUTIQUES:
        if b.statut != StatutBoutique.active:
            continue
        stock_alerte_b = len([s for s in stock_alerte if s.boutique_id == b.id])
        dettes_b = sum(d.solde_restant for d in dettes_clients if d.boutique_id == b.id)
        comparatif.append(
            LigneComparatifBoutique(
                boutique_id=b.id,
                nom=b.nom,
                secteurs=[s.value for s in b.secteurs],
                ca_jour=CA_JOUR.get(b.id, 0),
                stock_en_alerte=stock_alerte_b,
                dettes_en_cours=dettes_b,
            )
        )

    ca_jour_total = sum(CA_JOUR.values())

    return DashboardConsolide(
        chiffre_affaires_jour=ca_jour_total,
        marge_nette_jour=round(ca_jour_total * 0.27),
        dettes_clients_en_cours=total_dettes,
        produits_en_alerte_stock=len(stock_alerte),
        boutiques_concernees_alerte=len(boutiques_avec_alerte),
        transferts_en_transit=3,
        comparatif_boutiques=comparatif,
        alertes=[
            AlerteReseau(titre="Rupture de stock imminente", description="Riz local 25kg — Madina, moins de 6 unités restantes"),
            AlerteReseau(titre="Écart de caisse non justifié", description="Caisse secondaire — Kankan, écart de 45 000 GNF"),
            AlerteReseau(titre="Transfert en retard", description="Lansanaya → Kaloum, attendu depuis hier"),
            AlerteReseau(titre="Dette proche échéance", description="5 clients dépassent l'échéance sous 48h — Matam"),
        ],
    )
