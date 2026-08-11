from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import MODULES_IA
from app.core.security import get_current_user
from app.data.fixtures import (
    ANOMALIES_REPORTING,
    CHATBOT_CONFIG,
    CHATBOT_CONVERSATION_DEMO,
    SUGGESTIONS_REAPPRO,
    SYNTHESE_REPORTING,
)
from app.db_models.models import ProduitDB, UtilisateurDB
from app.models.schemas import AnomalieReporting, ConversationMessage, Produit

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
def catalogue_recherche(
    q: str | None = None,
    secteur: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[ProduitDB]:
    require_permission(db, current_user, MODULES_IA)
    query = db.query(ProduitDB)
    if secteur:
        query = query.filter(ProduitDB.secteur == secteur)
    if q:
        query = query.filter(ProduitDB.nom.ilike(f"%{q}%"))
    return query.all()


@router.get("/previsions", response_model=list[SuggestionAvecProduit])
def previsions_demande(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[SuggestionAvecProduit]:
    require_permission(db, current_user, MODULES_IA)
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
        if s.produit_id in produits_by_id
    ]


@router.get("/reporting", response_model=ReportingIntelligent)
def reporting_intelligent(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ReportingIntelligent:
    require_permission(db, current_user, MODULES_IA)
    return ReportingIntelligent(synthese=SYNTHESE_REPORTING, anomalies=ANOMALIES_REPORTING)


@router.get("/chatbot/config")
def chatbot_config(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> dict:
    require_permission(db, current_user, MODULES_IA)
    return CHATBOT_CONFIG


@router.get("/chatbot/conversation-demo", response_model=list[ConversationMessage])
def chatbot_conversation_demo(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[ConversationMessage]:
    require_permission(db, current_user, MODULES_IA)
    return CHATBOT_CONVERSATION_DEMO
