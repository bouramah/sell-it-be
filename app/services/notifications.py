"""Notifications déclenchées par les événements métier (cf. CDC §6.1 :
"Système de notification multicanal ... pour les commandes, livraisons,
relances de dettes"). Best-effort : un échec d'envoi est journalisé mais ne
doit jamais faire échouer l'opération métier qui le déclenche (création de
commande, affectation de livraison, etc.) — d'où l'absence d'exception levée
ici, contrairement à /dettes/{id}/rappel-sms qui est un envoi explicite.

Deux canaux : SMS pour les tiers externes (clients, fournisseurs — pas de
compte dans l'appli), push pour le personnel équipé de l'appli mobile
(gérants, livreurs) — qui reçoit en plus une notification in-app quand un
push_token est enregistré, sans attendre de rafraîchir un écran.
"""
import logging

from sqlalchemy.orm import Session

from app.db_models.models import BoutiqueDB, ClientDB, UtilisateurDB
from app.services.push import envoyer_notification_push
from app.services.sms import get_sms_provider

logger = logging.getLogger("kfstore.notifications")


def _send(to: str, message: str) -> None:
    try:
        if not get_sms_provider().send(to, message):
            logger.warning("Échec envoi SMS notification à %s", to)
    except Exception:
        logger.exception("Erreur envoi SMS notification à %s", to)


def _push(utilisateur: UtilisateurDB, titre: str, message: str) -> None:
    if not utilisateur.push_token:
        return
    try:
        if not envoyer_notification_push(utilisateur.push_token, titre, message):
            logger.warning("Échec envoi push notification à l'utilisateur %s", utilisateur.id)
    except Exception:
        logger.exception("Erreur envoi push notification à l'utilisateur %s", utilisateur.id)


def notifier_client(db: Session, client_nom: str, message: str) -> None:
    client = db.query(ClientDB).filter(ClientDB.nom == client_nom).first()
    if client and client.contact:
        _send(client.contact, message)


def notifier_utilisateur(db: Session, utilisateur_id: str | None, titre: str, message: str) -> None:
    """Notification push directe à un membre du personnel (ex. livreur affecté à une livraison)."""
    if not utilisateur_id:
        return
    u = db.get(UtilisateurDB, utilisateur_id)
    if u:
        _push(u, titre, message)


def notifier_gerants_boutique(db: Session, boutique_id: str, message: str, titre: str = "KFSTORE") -> None:
    gerants = (
        db.query(UtilisateurDB)
        .join(UtilisateurDB.boutiques)
        .filter(BoutiqueDB.id == boutique_id, UtilisateurDB.role == "gerant", UtilisateurDB.statut == "actif")
        .all()
    )
    for g in gerants:
        _send(g.contact, message)
        _push(g, titre, message)


def nom_boutique(db: Session, boutique_id: str) -> str:
    b = db.get(BoutiqueDB, boutique_id)
    return b.nom if b else boutique_id
