from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, status
from app.core.database import get_db
from app.core.security import create_access_token, get_current_user, verify_password
from app.db_models.models import UtilisateurDB
from app.models.write_schemas import LoginRequest, TokenResponse, UtilisateurConnecte

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(UtilisateurDB).filter(UtilisateurDB.contact == payload.contact).first()
    if not user or not verify_password(payload.mot_de_passe, user.mot_de_passe_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Numéro ou mot de passe incorrect")
    if user.statut != "actif":
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
