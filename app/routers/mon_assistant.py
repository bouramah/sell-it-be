"""Assistant IA — service client (CDC §4.4, phase 1 MVP) : répond aux questions du client sur
ses propres commandes et son crédit, avec le contexte réel de son compte (jamais celui d'un
autre client — même scoping strict que mes_commandes.py/mon_credit.py). Passe par IaProvider
(app/services/ia_provider.py), interchangeable sans réécriture (CDC §6.2)."""
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_client
from app.db_models.models import ClientDB, CommandeClientDB, DetteDB, ParametreApplicationDB
from app.models.schemas import StatutCommandeClient, TiersType
from app.services.ia_provider import get_ia_provider

router = APIRouter(prefix="/api/v1/mon-assistant", tags=["mon-assistant"])

MAX_MESSAGE = 2000
MAX_HISTORIQUE = 10

MESSAGE_INDISPONIBLE = "L'assistant IA est temporairement désactivé. Contactez votre boutique pour toute question."


class MessageHistorique(BaseModel):
    auteur: str  # "client" | "bot"
    texte: str


class MessageAssistantRequest(BaseModel):
    message: str
    historique: list[MessageHistorique] = []


class MessageAssistantResponse(BaseModel):
    reponse: str


def _contexte_client(db: Session, client: ClientDB) -> str:
    commandes = (
        db.query(CommandeClientDB)
        .filter(CommandeClientDB.client_id == client.id)
        .order_by(CommandeClientDB.date_creation.desc())
        .limit(5)
        .all()
    )
    dettes = db.query(DetteDB).filter(DetteDB.client_id == client.id, DetteDB.tiers_type == TiersType.client).all()
    solde_dette = sum(d.solde_restant for d in dettes)

    lignes_commandes = "\n".join(
        f"- Commande #{c.id} : statut {c.statut.value}, {c.montant:,.0f} GNF, passée le {c.date_creation.date().isoformat()}".replace(",", " ")
        for c in commandes
    ) or "Aucune commande passée pour le moment."

    return (
        f"Client : {client.nom} ({client.contact}).\n"
        f"Crédit autorisé : {'oui' if client.credit_autorise else 'non'}. "
        f"Solde de dette actuel : {solde_dette:,.0f} GNF.\n".replace(",", " ")
        + f"5 dernières commandes :\n{lignes_commandes}"
    )


SYSTEM_PROMPT = (
    "Tu es l'assistant service client de KFSTORE, un réseau de boutiques multi-secteurs "
    "(alimentation, habillement, électroménager) en Guinée. Réponds en français, de façon "
    "brève et directe (2-4 phrases). Tu peux répondre aux questions sur : le suivi des "
    "commandes du client, son solde de crédit/dette, et des questions générales sur le "
    "fonctionnement du service (livraison, paiement, retours). "
    "Règle stricte : n'utilise QUE les informations du contexte client fourni ci-dessous — "
    "n'invente jamais de numéro de commande, de montant ou de statut qui n'y figure pas. "
    "Si la question sort de ce périmètre (ex: demande de remboursement à traiter, litige, "
    "négociation de prix), réponds que tu transmets la demande à un opérateur de la boutique.\n\n"
    "Contexte du client actuellement connecté :\n{contexte}"
)


@router.post("/message", response_model=MessageAssistantResponse)
def envoyer_message(
    payload: MessageAssistantRequest,
    client: ClientDB = Depends(get_current_client),
    db: Session = Depends(get_db),
) -> MessageAssistantResponse:
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Le message ne peut pas être vide")
    if len(payload.message) > MAX_MESSAGE:
        raise HTTPException(status_code=400, detail=f"Message trop long (max {MAX_MESSAGE} caractères)")

    toggle = db.get(ParametreApplicationDB, "chatbot_actif")
    if toggle is not None and not toggle.actif:
        return MessageAssistantResponse(reponse=MESSAGE_INDISPONIBLE)

    system = SYSTEM_PROMPT.format(contexte=_contexte_client(db, client))
    historique = payload.historique[-MAX_HISTORIQUE:]
    messages = [
        {"role": "user" if h.auteur == "client" else "assistant", "content": h.texte} for h in historique
    ]
    messages.append({"role": "user", "content": payload.message})

    reponse = get_ia_provider().repondre(system, messages)
    return MessageAssistantResponse(reponse=reponse)
