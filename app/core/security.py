from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.config import settings
from app.core.database import get_db
from app.db_models.models import ClientDB, UtilisateurDB
from app.services.securite import parametre_actif

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
# auto_error=False : ce schéma ne sert que pour la doc Swagger de l'API client (facultative) —
# get_current_client lève lui-même le 401 avec un message adapté à ce canal.
oauth2_scheme_client = OAuth2PasswordBearer(tokenUrl="/api/v1/client-auth/verifier-code", auto_error=False)

DEFAULT_PASSWORD = "kfstore2026"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str) -> str:
    """Jeton du personnel (web/mobile interne) — jamais accepté par get_current_client, et
    inversement, grâce au claim "typ" (cf. get_current_user/get_current_client ci-dessous)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": subject, "typ": "staff", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_client_token(subject: str) -> str:
    """Jeton de l'appli mobile client (grand public) — même secret/algorithme que le
    personnel, mais claim "typ" distinct : un client authentifié n'a jamais accès aux routes
    internes, et un token du personnel n'est jamais accepté sur les routes client (CDC §7.1 :
    "sans exposer de droits internes à ce canal")."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": subject, "typ": "client", "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> UtilisateurDB:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants invalides",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        contact = payload.get("sub")
        if contact is None or payload.get("typ") != "staff":
            raise credentials_error
    except JWTError:
        raise credentials_error

    user = db.query(UtilisateurDB).filter(UtilisateurDB.contact == contact).first()
    if user is None:
        raise credentials_error

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if parametre_actif(db, "expiration_session") and user.derniere_activite:
        limite = user.derniere_activite + timedelta(minutes=settings.session_inactivite_minutes)
        if now > limite:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expirée après inactivité, veuillez vous reconnecter",
                headers={"WWW-Authenticate": "Bearer"},
            )
    user.derniere_activite = now
    db.commit()
    return user


def get_current_client(token: str | None = Depends(oauth2_scheme_client), db: Session = Depends(get_db)) -> ClientDB:
    """Équivalent de get_current_user pour l'appli mobile client — jamais de vérrouillage/2FA/
    matrice de droits ici (CDC §6.1 : "sans exposer de droits internes à ce canal"), juste une
    identité client valide. Session à durée fixe (pas d'expiration par inactivité — un client
    n'utilise pas un poste partagé en boutique, contrairement au personnel)."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Connexion requise",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_error
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        contact = payload.get("sub")
        if contact is None or payload.get("typ") != "client":
            raise credentials_error
    except JWTError:
        raise credentials_error

    client = db.query(ClientDB).filter(ClientDB.contact == contact).first()
    if client is None:
        raise credentials_error
    return client
