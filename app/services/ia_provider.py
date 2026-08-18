"""Fournisseur LLM, abstrait derrière une interface interchangeable (cf. CDC §6.2 :
"pouvoir changer de fournisseur sans refonte") — même principe que app/services/sms.py.

Fournisseur par défaut : aucun appel externe, réponse honnête indiquant que l'assistant
n'est pas configuré. Bascule automatiquement sur OpenAI dès que OPENAI_API_KEY est renseignée.
"""
import logging
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger("kfstore.ia")

MESSAGE_NON_CONFIGURE = (
    "L'assistant IA n'est pas encore configuré côté serveur (aucune clé fournisseur LLM "
    "renseignée). Contactez le support KFSTORE pour cette demande."
)


class IaProvider(ABC):
    @abstractmethod
    def repondre(self, system: str, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        """Envoie [system + messages] au LLM et renvoie le texte de la réponse.
        Si json_mode=True, demande une réponse JSON stricte (l'appelant reste responsable
        du parsing et doit gérer un échec de parsing, le LLM n'étant jamais garanti fiable
        à 100% même en mode JSON)."""


class FixtureIaProvider(IaProvider):
    """Fournisseur par défaut tant qu'aucune clé n'est renseignée — ne fait aucun appel
    réseau, répond honnêtement plutôt que d'échouer ou d'halluciner une réponse."""

    def repondre(self, system: str, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        logger.info("[IA:fixture] clé OpenAI absente — réponse de repli renvoyée")
        return MESSAGE_NON_CONFIGURE


class OpenAiIaProvider(IaProvider):
    def __init__(self, api_key: str, model: str):
        self.model = model
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)

    def repondre(self, system: str, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        try:
            kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, *messages],
                temperature=0.3,
                max_tokens=500,
                **kwargs,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # erreurs réseau/API/quota du SDK, non typées finement
            logger.error("Échec appel OpenAI : %s", exc)
            return MESSAGE_NON_CONFIGURE


def get_ia_provider() -> IaProvider:
    if settings.openai_api_key:
        return OpenAiIaProvider(settings.openai_api_key, settings.openai_model)
    return FixtureIaProvider()
