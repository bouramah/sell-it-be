"""Assistant IA — service client (CDC §4.4, phase 1 MVP) : répond aux questions du client sur
ses propres commandes et son crédit, avec le contexte réel de son compte (jamais celui d'un
autre client — même scoping strict que mes_commandes.py/mon_credit.py). Passe par IaProvider
(app/services/ia_provider.py), interchangeable sans réécriture (CDC §6.2)."""
import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_client
from app.db_models.models import (
    BoutiqueDB,
    ClientDB,
    CommandeClientDB,
    DemandeCreditDB,
    DetteDB,
    MessageAssistantDB,
    ParametreApplicationDB,
    ProduitDB,
)
from app.models.schemas import StatutBoutique, StatutCommandeClient, TiersType
from app.services.ia_provider import get_ia_provider

router = APIRouter(prefix="/api/v1/mon-assistant", tags=["mon-assistant"])

MAX_MESSAGE = 2000
MAX_HISTORIQUE = 10
MAX_HISTORIQUE_CHARGEE = 50

MESSAGE_INDISPONIBLE = "L'assistant IA est temporairement désactivé. Contactez votre boutique pour toute question."


class MessageHistorique(BaseModel):
    auteur: str  # "client" | "bot"
    texte: str


class MessageAssistantRequest(BaseModel):
    message: str
    historique: list[MessageHistorique] = []


class MessageAssistantResponse(BaseModel):
    reponse: str


class MessageStocke(BaseModel):
    auteur: str
    texte: str
    horodatage: datetime


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

    produit_ids = {l.produit_id for c in commandes for l in c.lignes}
    produits_by_id = {p.id: p for p in db.query(ProduitDB).filter(ProduitDB.id.in_(produit_ids)).all()} if produit_ids else {}

    def _articles(c: CommandeClientDB) -> str:
        return ", ".join(
            f"{l.quantite}x {produits_by_id[l.produit_id].nom if l.produit_id in produits_by_id else l.produit_id} "
            f"({l.prix_unitaire:,.0f} GNF/unité)".replace(",", " ")
            for l in c.lignes
        ) or "aucun article"

    lignes_commandes = "\n".join(
        f"- Commande #{c.id} : statut {c.statut.value}, total {c.montant:,.0f} GNF, passée le "
        f"{c.date_creation.date().isoformat()}. Articles : {_articles(c)}.".replace(",", " ")
        for c in commandes
    ) or "Aucune commande passée pour le moment."

    demandes = (
        db.query(DemandeCreditDB)
        .filter(DemandeCreditDB.client_id == client.id)
        .order_by(DemandeCreditDB.date_creation.desc())
        .limit(3)
        .all()
    )
    lignes_demandes = "\n".join(
        f"- Demande de crédit du {d.date_creation.date().isoformat()} : {d.montant_souhaite:,.0f} GNF, "
        f"statut {d.statut.value}, motif « {d.motif} ».".replace(",", " ")
        for d in demandes
    ) or "Aucune demande de crédit en cours."

    boutiques = db.query(BoutiqueDB).filter(BoutiqueDB.statut == StatutBoutique.active).all()
    lignes_boutiques = "\n".join(
        f"- {b.nom} : {b.quartier}, {b.commune}, {b.ville}. Horaires : {b.horaires}. Tél : {b.telephone}."
        for b in boutiques
    ) or "Aucune boutique active."

    return (
        f"Client : {client.nom} ({client.contact}).\n"
        f"Crédit autorisé sur ce compte : {'oui' if client.credit_autorise else 'non'}. "
        f"Solde de dette actuel : {solde_dette:,.0f} GNF.\n".replace(",", " ")
        + f"5 dernières commandes :\n{lignes_commandes}\n\n"
        + f"Demandes de crédit récentes :\n{lignes_demandes}\n\n"
        + f"Boutiques du réseau actuellement ouvertes :\n{lignes_boutiques}"
    )


# Faits fixes sur le fonctionnement réel de KFSTORE — pour que l'assistant réponde avec
# assurance aux questions générales sur l'appli (pas seulement aux questions nécessitant les
# données du compte), sans jamais inventer une règle qui n'existe pas dans le produit réel.
FONCTIONNEMENT_KFSTORE = """
- Compte client : inscription automatique au premier code reçu par SMS, aucun mot de passe.
  Le nom peut être modifié depuis Compte > Modifier mon nom.
- Catalogue : consultable sans connexion. Se connecter n'est nécessaire qu'au moment de
  commander. Recherche et filtres par secteur (alimentation générale, habillement, électronique/
  électroménager) et par boutique.
- Commande : on choisit une boutique disponible pour le produit, on ajoute au panier, puis on
  valide avec un mode de paiement. Statuts possibles, dans l'ordre : en attente → confirmée →
  en préparation → en livraison → livrée (ou annulée à tout moment par la boutique).
- Modes de paiement actuellement disponibles : paiement en boutique (espèces), paiement à la
  livraison, et crédit client si le compte y est autorisé. Le Mobile Money est prévu mais pas
  encore activé (bouton visible mais désactivé dans l'appli).
- Crédit : doit d'abord être activé par une boutique physiquement (le client ne peut pas
  l'activer lui-même). Une fois autorisé, il peut demander un crédit depuis Compte > Mon crédit
  — la demande reste "en attente" jusqu'à validation par un responsable de boutique, jamais
  automatique.
- Remboursement d'une dette : le client peut signaler depuis l'appli qu'il a remboursé, mais
  cela ne fait qu'avertir la boutique — l'encaissement réel et la mise à jour du solde sont
  toujours faits par un employé après vérification, jamais automatiquement depuis l'appli.
- Facture : téléchargeable en PDF depuis le détail de chaque commande.
- Livraison : gérée par la boutique qui traite la commande ; pas de suivi géolocalisé en temps
  réel actuellement, seulement le statut de la commande.
""".strip()

SYSTEM_PROMPT = (
    "Tu es l'assistant service client de KFSTORE, un réseau de boutiques multi-secteurs "
    "(alimentation, habillement, électroménager) en Guinée, disponible dans l'appli mobile "
    "client. Réponds en français, de façon brève et directe (2-5 phrases). Ton rôle couvre "
    "TOUT ce qu'un client peut légitimement demander sur l'appli et son propre compte : suivi "
    "détaillé de ses commandes (y compris quels articles elles contiennent), son crédit et sa "
    "dette, les boutiques du réseau, et le fonctionnement général du service (comment "
    "commander, modes de paiement, comment le crédit et les remboursements fonctionnent, etc.). "
    "N'élude pas une question qui est couverte par les informations ci-dessous — réponds "
    "directement et complètement plutôt que de renvoyer vers un opérateur.\n\n"
    "Comment fonctionne KFSTORE (informations générales, toujours vraies) :\n"
    f"{FONCTIONNEMENT_KFSTORE}\n\n"
    "Règle stricte sur les données personnelles : pour tout ce qui concerne CE client précis "
    "(numéro de commande, montant, statut, contenu d'une commande, solde de dette...), "
    "n'utilise QUE le contexte fourni ci-dessous — n'invente jamais une donnée qui n'y figure "
    "pas. Si une question porte sur autre chose que l'appli KFSTORE, ou nécessite une action "
    "que seul un humain peut faire (litige, négociation de prix, réclamation), dis que tu "
    "transmets la demande à un opérateur de la boutique.\n\n"
    "Contexte du client actuellement connecté :\n{contexte}"
)


@router.get("/historique", response_model=list[MessageStocke])
def historique_conversation(
    client: ClientDB = Depends(get_current_client),
    db: Session = Depends(get_db),
) -> list[MessageStocke]:
    """Conversation passée avec l'assistant — sans ça, l'historique serait perdu à chaque
    fois que l'utilisateur quitte l'écran (état local uniquement côté appli)."""
    messages = (
        db.query(MessageAssistantDB)
        .filter(MessageAssistantDB.client_id == client.id)
        .order_by(MessageAssistantDB.horodatage.desc())
        .limit(MAX_HISTORIQUE_CHARGEE)
        .all()
    )
    messages.reverse()
    return [MessageStocke(auteur=m.auteur, texte=m.texte, horodatage=m.horodatage) for m in messages]


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

    maintenant = datetime.utcnow()
    db.add(MessageAssistantDB(id=str(uuid.uuid4())[:8], client_id=client.id, auteur="client", texte=payload.message, horodatage=maintenant))
    db.add(MessageAssistantDB(id=str(uuid.uuid4())[:8], client_id=client.id, auteur="bot", texte=reponse, horodatage=maintenant))
    db.commit()

    return MessageAssistantResponse(reponse=reponse)
