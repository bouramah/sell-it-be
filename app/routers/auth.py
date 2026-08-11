import random
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import get_db
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.db_models.models import OtpCodeDB, UtilisateurDB
from app.models.write_schemas import (
    LoginRequest,
    MotDePasseOublieRequest,
    ReinitialisationMotDePasseRequest,
    TokenResponse,
    UtilisateurConnecte,
)
from app.services.audit import log_audit
from app.services.sms import get_sms_provider

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

OTP_DUREE_VALIDITE = timedelta(minutes=10)
OTP_DELAI_RENVOI = timedelta(seconds=60)

MESSAGE_GENERIQUE = "Si ce numéro est associé à un compte, un code de vérification a été envoyé par SMS."


class MessageResponse(BaseModel):
    message: str


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(UtilisateurDB).filter(UtilisateurDB.contact == payload.contact).first()
    if not user or not verify_password(payload.mot_de_passe, user.mot_de_passe_hash):
        log_audit(db, f"Connexion échouée — {payload.contact}", payload.contact)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Numéro ou mot de passe incorrect")
    if user.statut != "actif":
        log_audit(db, "Connexion refusée — compte inactif", f"{user.prenom} {user.nom}")
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte inactif")
    token = create_access_token(subject=user.contact)
    return TokenResponse(access_token=token)


@router.get("/moi", response_model=UtilisateurConnecte)
def moi(current_user: UtilisateurDB = Depends(get_current_user)) -> UtilisateurConnecte:
    return UtilisateurConnecte(
        id=current_user.id,
        nom=current_user.nom,
        prenom=current_user.prenom,
        contact=current_user.contact,
        role=current_user.role,
        boutique_ids=[b.id for b in current_user.boutiques],
    )


@router.post("/mot-de-passe-oublie", response_model=MessageResponse)
def mot_de_passe_oublie(payload: MotDePasseOublieRequest, db: Session = Depends(get_db)) -> MessageResponse:
    # Réponse volontairement identique que le contact existe ou non, pour ne pas
    # permettre l'énumération des comptes existants via ce point d'entrée public.
    user = db.query(UtilisateurDB).filter(UtilisateurDB.contact == payload.contact).first()
    if not user:
        return MessageResponse(message=MESSAGE_GENERIQUE)

    now = datetime.now(timezone.utc)
    recent = (
        db.query(OtpCodeDB)
        .filter(OtpCodeDB.contact == payload.contact, OtpCodeDB.used.is_(False), OtpCodeDB.created_at > now - OTP_DELAI_RENVOI)
        .first()
    )
    if recent:
        return MessageResponse(message=MESSAGE_GENERIQUE)

    db.query(OtpCodeDB).filter(OtpCodeDB.contact == payload.contact, OtpCodeDB.used.is_(False)).update({"used": True})

    code = f"{random.randint(0, 999999):06d}"
    db.add(OtpCodeDB(
        id=str(uuid.uuid4())[:8], contact=payload.contact, code_hash=hash_password(code),
        created_at=now, expires_at=now + OTP_DUREE_VALIDITE, used=False,
    ))
    get_sms_provider().send(payload.contact, f"KFSTORE — votre code de réinitialisation : {code} (valable 10 minutes).")
    log_audit(db, f"Code de réinitialisation envoyé — {user.prenom} {user.nom}", payload.contact)
    db.commit()
    return MessageResponse(message=MESSAGE_GENERIQUE)


@router.post("/reinitialiser-mot-de-passe", response_model=MessageResponse)
def reinitialiser_mot_de_passe(payload: ReinitialisationMotDePasseRequest, db: Session = Depends(get_db)) -> MessageResponse:
    erreur = HTTPException(status_code=400, detail="Code invalide ou expiré")
    user = db.query(UtilisateurDB).filter(UtilisateurDB.contact == payload.contact).first()
    if not user:
        raise erreur

    now = datetime.now(timezone.utc)
    otp = (
        db.query(OtpCodeDB)
        .filter(OtpCodeDB.contact == payload.contact, OtpCodeDB.used.is_(False), OtpCodeDB.expires_at > now)
        .order_by(OtpCodeDB.created_at.desc())
        .first()
    )
    if not otp or not verify_password(payload.code, otp.code_hash):
        raise erreur

    otp.used = True
    user.mot_de_passe_hash = hash_password(payload.nouveau_mot_de_passe)
    log_audit(db, f"Mot de passe réinitialisé via SMS — {user.prenom} {user.nom}", payload.contact)
    db.commit()
    return MessageResponse(message="Mot de passe réinitialisé avec succès.")
