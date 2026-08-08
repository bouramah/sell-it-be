from pydantic import BaseModel

from fastapi import APIRouter
from app.data.fixtures import BOUTIQUES, PRODUITS, STOCKS
from app.models.schemas import StatutBoutique

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


class TopBoutique(BaseModel):
    boutique_id: str
    nom: str
    ville: str
    chiffre_affaires: float


class AlerteStock(BaseModel):
    boutique_id: str
    boutique_nom: str
    produit_nom: str
    quantite_disponible: int
    seuil_alerte: int


class DashboardConsolide(BaseModel):
    chiffre_affaires: float
    marge: float
    stock_total_valorise: float
    dettes_creances_en_cours: float
    depenses_mois: float
    nb_boutiques_actives: int
    nb_boutiques_total: int
    top_boutiques: list[TopBoutique]
    alertes_stock: list[AlerteStock]


# Chiffre d'affaires simulé par boutique (le module ventes n'est pas encore branché)
CA_SIMULE = {
    "btq-lansanaya": 48_500_000,
    "btq-matam": 21_300_000,
    "btq-madina": 33_900_000,
    "btq-kankan": 17_650_000,
    "btq-labe": 0,
    "btq-ratoma-old": 0,
}


@router.get("", response_model=DashboardConsolide)
def get_dashboard() -> DashboardConsolide:
    produits_by_id = {p.id: p for p in PRODUITS}
    boutiques_by_id = {b.id: b for b in BOUTIQUES}

    stock_total_valorise = sum(
        s.quantite_disponible * produits_by_id[s.produit_id].prix for s in STOCKS
    )
    chiffre_affaires = sum(CA_SIMULE.values())
    marge = chiffre_affaires * 0.28  # taux de marge indicatif pour le prototype

    top_boutiques = sorted(
        (
            TopBoutique(
                boutique_id=b.id,
                nom=b.nom,
                ville=b.ville,
                chiffre_affaires=CA_SIMULE.get(b.id, 0),
            )
            for b in BOUTIQUES
            if b.statut == StatutBoutique.active
        ),
        key=lambda t: t.chiffre_affaires,
        reverse=True,
    )

    alertes_stock = [
        AlerteStock(
            boutique_id=s.boutique_id,
            boutique_nom=boutiques_by_id[s.boutique_id].nom,
            produit_nom=produits_by_id[s.produit_id].nom,
            quantite_disponible=s.quantite_disponible,
            seuil_alerte=s.seuil_alerte,
        )
        for s in STOCKS
        if s.quantite_disponible <= s.seuil_alerte
    ]

    return DashboardConsolide(
        chiffre_affaires=chiffre_affaires,
        marge=marge,
        stock_total_valorise=stock_total_valorise,
        dettes_creances_en_cours=6_250_000,
        depenses_mois=4_120_000,
        nb_boutiques_actives=sum(1 for b in BOUTIQUES if b.statut == StatutBoutique.active),
        nb_boutiques_total=len(BOUTIQUES),
        top_boutiques=top_boutiques,
        alertes_stock=alertes_stock,
    )
