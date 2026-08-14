"""Notifications push vers l'appli mobile, via l'API Expo Push (cf. CDC §6.1 :
"Système de notification multicanal"). Contrairement au SMS, l'API Expo Push
est gratuite et ne nécessite aucun compte fournisseur — utilisable directement
en développement comme en production, dès qu'un token push valide est
enregistré (PUT /utilisateurs/me/push-token). Best-effort : un échec n'est
jamais levé en exception, seulement journalisé, à l'image de services/sms.py.
"""
import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger("kfstore.push")

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def envoyer_notification_push(token: str, titre: str, message: str) -> bool:
    """Envoie une notification push à un token Expo. Renvoie True si l'appel API
    a réussi (ne garantit pas la remise effective sur l'appareil)."""
    payload = json.dumps({"to": token, "title": titre, "body": message, "sound": "default"}).encode()
    request = urllib.request.Request(
        EXPO_PUSH_URL, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except urllib.error.URLError as exc:
        logger.error("Échec envoi notification push à %s : %s", token, exc)
        return False
