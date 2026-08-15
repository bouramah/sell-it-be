from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.core.config import settings
from app.core.database import get_db
from app.db_models.models import UtilisateurDB
from app.services.securite import parametre_actif

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

DEFAULT_PASSWORD = "kfstore2026"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": subject, "exp": expire}
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
        if contact is None:
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
