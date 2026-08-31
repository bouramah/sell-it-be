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
    ChangementMotDePasseRequest,
    LoginRequest,
    MotDePasseOublieRequest,
    PushTokenUpdate,
    ReinitialisationMotDePasseRequest,
    TokenResponse,
    UtilisateurConnecte,
    Verifier2FARequest,
)
from app.services.audit import log_audit
from app.services.securite import parametre_actif
from app.services.sms import get_sms_provider

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

OTP_DUREE_VALIDITE = timedelta(minutes=10)
OTP_DELAI_RENVOI = timedelta(seconds=60)

# Verrouillage de compte après tentatives échouées (CDC §7.1) — piloté par le paramètre
# de sécurité "verrouillage_tentatives".
MAX_TENTATIVES_CONNEXION = 5
DUREE_VERROUILLAGE = timedelta(minutes=15)

# 2FA obligatoire pour les comptes à privilèges élevés (CDC §7.1) — piloté par le
# paramètre de sécurité "2fa". Volontairement basé sur le rôle (pas la matrice de
# permissions) : c'est une mesure de sécurité de connexion liée au niveau de
# privilège du compte, pas un droit d'accès à une donnée.
ROLES_2FA_OBLIGATOIRE = {"administrateur", "gerant", "responsable_achats"}
OTP_DUREE_VALIDITE_2FA = timedelta(minutes=5)

MESSAGE_GENERIQUE = "Si ce numéro est associé à un compte, un code de vérification a été envoyé par SMS."


class MessageResponse(BaseModel):
    message: str


def _now_naive() -> datetime:
    """Les colonnes DateTime de la base ne portent pas de fuseau — par convention dans ce
    projet, toute valeur qui y est écrite est en UTC ; on compare donc ici avec une valeur
    UTC elle-même dépouillée de son tzinfo, pour rester comparable à ce qui vient d'être
    relu depuis la base (qui revient toujours naïf)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _envoyer_otp_connexion(db: Session, user: UtilisateurDB) -> None:
    now = _now_naive()
    db.query(OtpCodeDB).filter(
        OtpCodeDB.contact == user.contact, OtpCodeDB.objectif == "connexion", OtpCodeDB.used.is_(False)
    ).update({"used": True})
    code = f"{random.randint(0, 999999):06d}"
    db.add(OtpCodeDB(
        id=str(uuid.uuid4())[:8], contact=user.contact, code_hash=hash_password(code), code_clair=code,
        objectif="connexion", created_at=now, expires_at=now + OTP_DUREE_VALIDITE_2FA, used=False,
    ))
    get_sms_provider().send(user.contact, f"KFSTORE — votre code de connexion : {code} (valable 5 minutes).")
    log_audit(db, "Code de connexion (2FA) envoyé", f"{user.prenom} {user.nom}")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(UtilisateurDB).filter(UtilisateurDB.contact == payload.contact).first()

    if user and user.verrouille_jusqua and user.verrouille_jusqua > _now_naive():
        minutes_restantes = max(1, int((user.verrouille_jusqua - _now_naive()).total_seconds() // 60) + 1)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Compte verrouillé après plusieurs tentatives échouées. Réessayez dans {minutes_restantes} min.",
        )

    if not user or not verify_password(payload.mot_de_passe, user.mot_de_passe_hash):
        log_audit(db, f"Connexion échouée — {payload.contact}", payload.contact)
        if user and parametre_actif(db, "verrouillage_tentatives"):
            user.tentatives_echouees += 1
            if user.tentatives_echouees >= MAX_TENTATIVES_CONNEXION:
                user.verrouille_jusqua = _now_naive() + DUREE_VERROUILLAGE
                log_audit(
                    db, f"Compte verrouillé après {MAX_TENTATIVES_CONNEXION} tentatives échouées",
                    f"{user.prenom} {user.nom}",
                )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Numéro ou mot de passe incorrect")
    if user.statut != "actif":
        log_audit(db, "Connexion refusée — compte inactif", f"{user.prenom} {user.nom}")
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte inactif")

    user.tentatives_echouees = 0
    user.verrouille_jusqua = None

    if user.role in ROLES_2FA_OBLIGATOIRE and parametre_actif(db, "2fa"):
        _envoyer_otp_connexion(db, user)
        db.commit()
        return TokenResponse(otp_requis=True)

    user.derniere_connexion = datetime.now(timezone.utc)
    user.derniere_activite = _now_naive()
    token = create_access_token(subject=user.contact)
    db.commit()
    return TokenResponse(access_token=token)


@router.post("/verifier-2fa", response_model=TokenResponse)
def verifier_2fa(payload: Verifier2FARequest, db: Session = Depends(get_db)) -> TokenResponse:
    erreur = HTTPException(status_code=400, detail="Code invalide ou expiré")
    user = db.query(UtilisateurDB).filter(UtilisateurDB.contact == payload.contact).first()
    if not user:
        raise erreur

    now = _now_naive()
    otp = (
        db.query(OtpCodeDB)
        .filter(
            OtpCodeDB.contact == payload.contact, OtpCodeDB.objectif == "connexion",
            OtpCodeDB.used.is_(False), OtpCodeDB.expires_at > now,
        )
        .order_by(OtpCodeDB.created_at.desc())
        .first()
    )
    if not otp or not verify_password(payload.code, otp.code_hash):
        raise erreur

    otp.used = True
    user.derniere_connexion = datetime.now(timezone.utc)
    user.derniere_activite = now
    token = create_access_token(subject=user.contact)
    log_audit(db, "Connexion validée par code 2FA", f"{user.prenom} {user.nom}")
    db.commit()
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


@router.put("/moi/push-token", response_model=MessageResponse)
def enregistrer_push_token(
    payload: PushTokenUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> MessageResponse:
    """Enregistre (ou efface, si null — déconnexion) le token push Expo de
    l'appareil courant pour l'utilisateur connecté. Self-service : aucune
    permission particulière, chacun ne gère que son propre token."""
    current_user.push_token = payload.push_token
    db.commit()
    return MessageResponse(message="Token push enregistré")


@router.put("/moi/mot-de-passe", response_model=MessageResponse)
def changer_mot_de_passe(
    payload: ChangementMotDePasseRequest,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> MessageResponse:
    """Changement de mot de passe en libre-service par l'utilisateur connecté — distinct
    de la réinitialisation admin (SMS) et du flux mot-de-passe-oublié (OTP) : ici
    l'utilisateur est déjà authentifié, on vérifie juste le mot de passe actuel."""
    if not verify_password(payload.mot_de_passe_actuel, current_user.mot_de_passe_hash):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    current_user.mot_de_passe_hash = hash_password(payload.nouveau_mot_de_passe)
    log_audit(db, "Mot de passe modifié", f"{current_user.prenom} {current_user.nom}")
    db.commit()
    return MessageResponse(message="Mot de passe modifié")


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
        .filter(
            OtpCodeDB.contact == payload.contact, OtpCodeDB.objectif == "reinitialisation",
            OtpCodeDB.used.is_(False), OtpCodeDB.created_at > now - OTP_DELAI_RENVOI,
        )
        .first()
    )
    if recent:
        return MessageResponse(message=MESSAGE_GENERIQUE)

    db.query(OtpCodeDB).filter(
        OtpCodeDB.contact == payload.contact, OtpCodeDB.objectif == "reinitialisation", OtpCodeDB.used.is_(False)
    ).update({"used": True})

    code = f"{random.randint(0, 999999):06d}"
    db.add(OtpCodeDB(
        id=str(uuid.uuid4())[:8], contact=payload.contact, code_hash=hash_password(code), code_clair=code,
        objectif="reinitialisation", created_at=now, expires_at=now + OTP_DUREE_VALIDITE, used=False,
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
        .filter(
            OtpCodeDB.contact == payload.contact, OtpCodeDB.objectif == "reinitialisation",
            OtpCodeDB.used.is_(False), OtpCodeDB.expires_at > now,
        )
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
