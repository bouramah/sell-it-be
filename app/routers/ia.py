from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends
from app.core.database import get_db
from app.data.fixtures import (
    ANOMALIES_REPORTING,
    CHATBOT_CONFIG,
    CHATBOT_CONVERSATION_DEMO,
    SUGGESTIONS_REAPPRO,
    SYNTHESE_REPORTING,
)
from app.db_models.models import ProduitDB
from app.models.schemas import AnomalieReporting, ConversationMessage, Produit, Secteur

router = APIRouter(prefix="/api/v1/ia", tags=["ia"])


class SuggestionAvecProduit(BaseModel):
    produit_id: str
    produit_nom: str
    boutique_id: str
    stock_actuel: int
    ventes_prevues_14j: int
    quantite_suggeree: int


class ReportingIntelligent(BaseModel):
    synthese: str
    anomalies: list[AnomalieReporting]


@router.get("/catalogue", response_model=list[Produit])
def catalogue_recherche(q: str | None = None, secteur: Secteur | None = None, db: Session = Depends(get_db)) -> list[ProduitDB]:
    query = db.query(ProduitDB)
    if secteur:
        query = query.filter(ProduitDB.secteur == secteur)
    if q:
        query = query.filter(ProduitDB.nom.ilike(f"%{q}%"))
    return query.all()


@router.get("/previsions", response_model=list[SuggestionAvecProduit])
def previsions_demande(db: Session = Depends(get_db)) -> list[SuggestionAvecProduit]:
    produits_by_id = {p.id: p for p in db.query(ProduitDB).all()}
    return [
        SuggestionAvecProduit(
            produit_id=s.produit_id,
            produit_nom=produits_by_id[s.produit_id].nom,
            boutique_id=s.boutique_id,
            stock_actuel=s.stock_actuel,
            ventes_prevues_14j=s.ventes_prevues_14j,
            quantite_suggeree=s.quantite_suggeree,
        )
        for s in SUGGESTIONS_REAPPRO
    ]


@router.get("/reporting", response_model=ReportingIntelligent)
def reporting_intelligent() -> ReportingIntelligent:
    return ReportingIntelligent(synthese=SYNTHESE_REPORTING, anomalies=ANOMALIES_REPORTING)


@router.get("/chatbot/config")
def chatbot_config() -> dict:
    return CHATBOT_CONFIG


@router.get("/chatbot/conversation-demo", response_model=list[ConversationMessage])
def chatbot_conversation_demo() -> list[ConversationMessage]:
    return CHATBOT_CONVERSATION_DEMO
