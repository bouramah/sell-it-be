"""Authentification de l'appli mobile client — CDC §3.1/§6.1/§7.1 : "authentification adaptée
pour l'application mobile client (numéro de téléphone + code à usage unique), sans exposer de
droits internes à ce canal". Aucun mot de passe, aucune matrice de droits, aucune 2FA — un
client authentifié n'a accès qu'à ses propres données (commandes, crédit), jamais aux données
d'un autre client ni aux fonctions internes (cf. get_current_client dans app/core/security.py).

Auto-inscription (décision produit du 2026-08-15) : un numéro inconnu à la vérification du code
crée automatiquement un nouveau ClientDB (segment "nouveau", credit_autorise=False tant qu'une
boutique ne l'active pas explicitement) plutôt que de refuser la connexion — cohérent avec la
vocation grand public de cette appli (CDC §3.1 : "Version Mobile client... clients finaux...
dans toutes les villes couvertes")."""
import random
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import create_client_token, get_current_client, hash_password, verify_password
from app.db_models.models import ClientDB, OtpCodeDB
from app.models.schemas import Client, SegmentClient
from app.models.write_schemas import (
    ClientProfilUpdate,
    ClientTokenResponse,
    DemanderCodeClientRequest,
    VerifierCodeClientRequest,
)
from app.services.audit import log_audit
from app.services.sms import get_sms_provider

router = APIRouter(prefix="/api/v1/client-auth", tags=["client-auth"])

OTP_DUREE_VALIDITE = timedelta(minutes=10)
OTP_DELAI_RENVOI = timedelta(seconds=60)
OBJECTIF = "connexion_client"


class MessageResponse(BaseModel):
    message: str


@router.post("/demander-code", response_model=MessageResponse)
def demander_code(payload: DemanderCodeClientRequest, db: Session = Depends(get_db)) -> MessageResponse:
    now = datetime.now(timezone.utc)
    recent = (
        db.query(OtpCodeDB)
        .filter(OtpCodeDB.contact == payload.contact, OtpCodeDB.objectif == OBJECTIF, OtpCodeDB.used.is_(False), OtpCodeDB.created_at > now - OTP_DELAI_RENVOI)
        .first()
    )
    if recent:
        return MessageResponse(message="Un code a déjà été envoyé récemment, patientez avant d'en redemander un.")

    db.query(OtpCodeDB).filter(OtpCodeDB.contact == payload.contact, OtpCodeDB.objectif == OBJECTIF, OtpCodeDB.used.is_(False)).update({"used": True})

    code = f"{random.randint(0, 999999):06d}"
    db.add(OtpCodeDB(
        id=str(uuid.uuid4())[:8], contact=payload.contact, code_hash=hash_password(code), objectif=OBJECTIF,
        created_at=now, expires_at=now + OTP_DUREE_VALIDITE, used=False,
    ))
    get_sms_provider().send(payload.contact, f"KFSTORE — votre code de connexion : {code} (valable 10 minutes).")
    db.commit()
    return MessageResponse(message="Code envoyé par SMS.")


@router.post("/verifier-code", response_model=ClientTokenResponse)
def verifier_code(payload: VerifierCodeClientRequest, db: Session = Depends(get_db)) -> ClientTokenResponse:
    erreur = HTTPException(status_code=400, detail="Code invalide ou expiré")
    now = datetime.now(timezone.utc)
    otp = (
        db.query(OtpCodeDB)
        .filter(
            OtpCodeDB.contact == payload.contact, OtpCodeDB.objectif == OBJECTIF,
            OtpCodeDB.used.is_(False), OtpCodeDB.expires_at > now,
        )
        .order_by(OtpCodeDB.created_at.desc())
        .first()
    )
    if not otp or not verify_password(payload.code, otp.code_hash):
        raise erreur
    otp.used = True

    client = db.query(ClientDB).filter(ClientDB.contact == payload.contact).first()
    nouveau = client is None
    if client is None:
        client = ClientDB(
            id=str(uuid.uuid4())[:8], nom="Nouveau client", contact=payload.contact,
            segment=SegmentClient.nouveau, credit_autorise=False,
            created_by="Auto-inscription — appli mobile client", updated_by="Auto-inscription — appli mobile client",
        )
        db.add(client)
        log_audit(db, f"Nouveau client auto-inscrit via l'appli mobile — {payload.contact}", payload.contact)
    else:
        log_audit(db, "Connexion appli mobile client", f"{client.nom} ({client.contact})")

    token = create_client_token(subject=client.contact)
    db.commit()
    return ClientTokenResponse(access_token=token, nouveau_compte=nouveau)


@router.get("/moi", response_model=Client)
def moi(client: ClientDB = Depends(get_current_client), db: Session = Depends(get_db)) -> Client:
    from app.routers.clients import _to_schema  # import tardif : évite un import circulaire au chargement du module
    return _to_schema(client, db)


@router.put("/moi", response_model=Client)
def modifier_profil(
    payload: ClientProfilUpdate,
    client: ClientDB = Depends(get_current_client),
    db: Session = Depends(get_db),
) -> Client:
    from app.routers.clients import _to_schema
    client.nom = payload.nom
    client.quartier = payload.quartier
    client.commune = payload.commune
    client.ville = payload.ville
    client.secteur_geo_id = payload.secteur_geo_id
    client.updated_by = f"{client.nom} (self-service appli mobile)"
    db.commit()
    db.refresh(client)
    return _to_schema(client, db)
