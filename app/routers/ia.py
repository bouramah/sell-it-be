from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends
from app.core.authorization import require_role
from app.core.database import get_db
from app.core.security import get_current_user
from app.data.fixtures import (
    ANOMALIES_REPORTING,
    CHATBOT_CONFIG,
    CHATBOT_CONVERSATION_DEMO,
    SUGGESTIONS_REAPPRO,
    SYNTHESE_REPORTING,
)
from app.db_models.models import ProduitDB, UtilisateurDB
from app.models.schemas import AnomalieReporting, ConversationMessage, Produit, Role

router = APIRouter(prefix="/api/v1/ia", tags=["ia"])

# CDC 3.3 : "Accéder aux modules IA" — gérant (lecture), responsable achats, administrateur.
# Vendeur/caissier n'y figurent pas.
ROLES_IA = (Role.gerant, Role.responsable_achats, Role.administrateur)


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
    require_role(current_user, *ROLES_IA)
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
    require_role(current_user, *ROLES_IA)
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
def reporting_intelligent(current_user: UtilisateurDB = Depends(get_current_user)) -> ReportingIntelligent:
    require_role(current_user, *ROLES_IA)
    return ReportingIntelligent(synthese=SYNTHESE_REPORTING, anomalies=ANOMALIES_REPORTING)


@router.get("/chatbot/config")
def chatbot_config(current_user: UtilisateurDB = Depends(get_current_user)) -> dict:
    require_role(current_user, *ROLES_IA)
    return CHATBOT_CONFIG


@router.get("/chatbot/conversation-demo", response_model=list[ConversationMessage])
def chatbot_conversation_demo(current_user: UtilisateurDB = Depends(get_current_user)) -> list[ConversationMessage]:
    require_role(current_user, *ROLES_IA)
    return CHATBOT_CONVERSATION_DEMO
