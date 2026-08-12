"""Notifications SMS déclenchées par les événements métier (cf. CDC §6.1 :
"Système de notification multicanal ... pour les commandes, livraisons,
relances de dettes"). Best-effort : un échec d'envoi est journalisé mais ne
doit jamais faire échouer l'opération métier qui le déclenche (création de
commande, affectation de livraison, etc.) — d'où l'absence d'exception levée
ici, contrairement à /dettes/{id}/rappel-sms qui est un envoi explicite.
"""
import logging

from sqlalchemy.orm import Session

from app.db_models.models import BoutiqueDB, ClientDB, UtilisateurDB
from app.services.sms import get_sms_provider

logger = logging.getLogger("kfstore.notifications")


def _send(to: str, message: str) -> None:
    try:
        if not get_sms_provider().send(to, message):
            logger.warning("Échec envoi SMS notification à %s", to)
    except Exception:
        logger.exception("Erreur envoi SMS notification à %s", to)


def notifier_client(db: Session, client_nom: str, message: str) -> None:
    client = db.query(ClientDB).filter(ClientDB.nom == client_nom).first()
    if client and client.contact:
        _send(client.contact, message)


def notifier_gerants_boutique(db: Session, boutique_id: str, message: str) -> None:
    gerants = (
        db.query(UtilisateurDB)
        .join(UtilisateurDB.boutiques)
        .filter(BoutiqueDB.id == boutique_id, UtilisateurDB.role == "gerant", UtilisateurDB.statut == "actif")
        .all()
    )
    for g in gerants:
        _send(g.contact, message)


def nom_boutique(db: Session, boutique_id: str) -> str:
    b = db.get(BoutiqueDB, boutique_id)
    return b.nom if b else boutique_id
