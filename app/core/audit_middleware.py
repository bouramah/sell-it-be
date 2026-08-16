"""Traçage automatique de chaque requête API par utilisateur (CDC — traçabilité complète,
demande explicite : "tout ce qui se passe dans l'appli doit être tracé par user"). Contrairement
à un décorateur posé endpoint par endpoint, ce middleware ne peut pas être oublié sur un futur
endpoint : il couvre systématiquement toute requête sous /api/v1, y compris les consultations
(GET), pour le back-office web ET les deux applis mobiles (même backend, mêmes routes).

Un handler qui appelle déjà `log_audit()` avec un libellé métier riche (avant/après inclus)
n'est pas doublé — voir `current_audit_flag`/`AuditFlag` dans app/services/audit.py : ce
middleware pose un `AuditFlag` frais dans la contextvar avant d'appeler l'endpoint (les
endpoints `def` synchrones de FastAPI tournent dans un thread de threadpool, qui hérite d'une
copie du contexte — seule une MUTATION du flag déjà partagé traverse cette frontière, pas un
`ContextVar.set()` fait depuis le thread).
"""
import uuid
from datetime import datetime, timezone

from jose import JWTError, jwt
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.database import SessionLocal
from app.db_models.models import ClientDB, JournalAuditDB, UtilisateurDB
from app.services.audit import AuditFlag, current_audit_flag

_VERBES = {"GET": "Consultation", "POST": "Création", "PUT": "Modification", "PATCH": "Modification", "DELETE": "Suppression"}


def _est_identifiant(segment: str) -> bool:
    """Un segment de chemin qui ressemble à un id opaque (uuid tronqué, numérique...) plutôt
    qu'à un mot du libellé — ex. distinguer "valider" (une sous-action) de "a1b2c3d4" (un id)."""
    if segment.isdigit():
        return True
    return len(segment) >= 6 and all(c in "0123456789abcdef-" for c in segment.lower())


def _libelle_auto(method: str, path: str) -> str:
    chemin = path.removeprefix("/api/v1/")
    segments = [s for s in chemin.split("/") if s]
    ressource = segments[0].replace("-", " ") if segments else chemin
    verbe = _VERBES.get(method, method)
    sous_action = next((s for s in segments[1:] if not _est_identifiant(s)), None)
    if sous_action:
        return f"{verbe} — {ressource} ({sous_action.replace('-', ' ')})"
    return f"{verbe} — {ressource}"


def _tracer(method: str, path: str, headers: Headers, statut_code: int) -> None:
    canal = headers.get("x-client-canal", "inconnu")
    utilisateur_id: str | None = None
    client_id: str | None = None
    auteur = "Anonyme"

    db = SessionLocal()
    try:
        auth = headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            try:
                payload = jwt.decode(auth[7:], settings.jwt_secret, algorithms=[settings.jwt_algorithm])
                contact, typ = payload.get("sub"), payload.get("typ")
            except JWTError:
                contact, typ = None, None

            if contact and typ == "staff":
                user = db.query(UtilisateurDB).filter(UtilisateurDB.contact == contact).first()
                if user:
                    utilisateur_id, auteur = user.id, f"{user.prenom} {user.nom}"
            elif contact and typ == "client":
                client = db.query(ClientDB).filter(ClientDB.contact == contact).first()
                if client:
                    client_id, auteur = client.id, client.nom

        db.add(JournalAuditDB(
            id=str(uuid.uuid4())[:8],
            horodatage=datetime.now(timezone.utc),
            action=_libelle_auto(method, path),
            auteur=auteur,
            utilisateur_id=utilisateur_id,
            client_id=client_id,
            canal=canal,
            methode=method,
            chemin=path,
            statut_code=statut_code,
        ))
        db.commit()
    finally:
        db.close()


class AuditTraceMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path, method = scope["path"], scope["method"]
        if not path.startswith("/api/v1/") or method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        flag = AuditFlag()
        token = current_audit_flag.set(flag)
        statut_code = 500

        async def send_wrapper(message) -> None:
            nonlocal statut_code
            if message["type"] == "http.response.start":
                statut_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            current_audit_flag.reset(token)

        try:
            if not flag.logged:
                _tracer(method, path, Headers(scope=scope), statut_code)
        except Exception:
            # Le traçage ne doit jamais faire échouer une requête réelle.
            pass
