"""SMS sending, abstracted behind a provider interface (cf. CDC §7/§8.2 :
"Fournisseur de SMS/WhatsApp Business pour les notifications et campagnes").

Default provider is "console" — it doesn't send anything, just logs — so
password reset and notification flows work end-to-end in development
without any external account. Switch SMS_PROVIDER (+ SMS_API_KEY/SECRET/
SENDER_ID) once a real provider is chosen.
"""
import base64
import logging
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger("kfstore.sms")


class SmsProvider(ABC):
    @abstractmethod
    def send(self, to: str, message: str) -> bool:
        """Envoie un SMS. Renvoie True si l'envoi a réussi (ou a été simulé)."""


class ConsoleSmsProvider(SmsProvider):
    """Fournisseur par défaut : journalise le SMS au lieu de l'envoyer.
    Permet de développer/tester la réinitialisation de mot de passe et les
    notifications sans compte fournisseur SMS."""

    def send(self, to: str, message: str) -> bool:
        logger.info("[SMS:console] -> %s: %s", to, message)
        return True


class TwilioSmsProvider(SmsProvider):
    """Implémentation de référence via l'API REST Twilio. Nécessite
    SMS_API_KEY (Account SID), SMS_API_SECRET (Auth Token) et SMS_SENDER_ID
    (numéro Twilio expéditeur, au format E.164)."""

    def __init__(self, account_sid: str, auth_token: str, sender: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.sender = sender

    def send(self, to: str, message: str) -> bool:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        data = urllib.parse.urlencode({"To": to, "From": self.sender, "Body": message}).encode()
        credentials = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        request = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return 200 <= response.status < 300
        except urllib.error.URLError as exc:
            logger.error("Échec envoi SMS via Twilio à %s : %s", to, exc)
            return False


class NimbaSmsProvider(SmsProvider):
    """Fournisseur retenu pour KFSTORE (opérateur guinéen). Utilise le
    client officiel `nimbasms` — SMS_API_KEY = ACCOUNT_SID, SMS_API_SECRET
    = AUTH_TOKEN, SMS_SENDER_ID = nom d'expéditeur validé sur le compte
    Nimba (cf. https://developers.nimbasms.com/)."""

    def __init__(self, account_sid: str, auth_token: str, sender_name: str):
        from nimbasms import Client

        self.client = Client(account_sid, auth_token)
        self.sender_name = sender_name

    def send(self, to: str, message: str) -> bool:
        try:
            response = self.client.messages.create(to=[to], sender_name=self.sender_name, message=message)
        except Exception as exc:  # erreurs réseau/API du SDK, non typées
            logger.error("Échec envoi SMS via NimbaSMS à %s : %s", to, exc)
            return False
        if not response.ok:
            logger.error("Échec envoi SMS via NimbaSMS à %s : %s", to, response.data)
        return response.ok


def get_sms_provider() -> SmsProvider:
    if settings.sms_provider == "nimba" and settings.sms_api_key and settings.sms_api_secret:
        return NimbaSmsProvider(settings.sms_api_key, settings.sms_api_secret, settings.sms_sender_id)
    if settings.sms_provider == "twilio" and settings.sms_api_key and settings.sms_api_secret:
        return TwilioSmsProvider(settings.sms_api_key, settings.sms_api_secret, settings.sms_sender_id)
    return ConsoleSmsProvider()
