import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import ROLES_PORTEE_RESEAU, a_portee_reseau, assert_boutique_access, boutiques_autorisees, require_role
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import PromotionDB, UtilisateurDB
from app.models.schemas import OriginePromotion, Promotion, Role, StatutPromotion
from app.models.write_schemas import PromotionCreate, PromotionStatutUpdate

router = APIRouter(prefix="/api/v1/promotions", tags=["promotions"])

# CDC 3.3 : "Paramétrer les promotions et tarifs" = gérant (local, sous validation) + responsable
# achats + administrateur ; vendeur/caissier n'y figurent pas.
ROLES_PROMOTION_CREATION = (Role.gerant, Role.responsable_achats, Role.administrateur)


@router.get("", response_model=list[Promotion])
def list_promotions(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[PromotionDB]:
    query = db.query(PromotionDB)
    if not a_portee_reseau(current_user):
        autorisees = boutiques_autorisees(current_user)
        query = query.filter((PromotionDB.boutique_id.in_(autorisees)) | (PromotionDB.boutique_id.is_(None)))
    if boutique_id:
        query = query.filter((PromotionDB.boutique_id == boutique_id) | (PromotionDB.boutique_id.is_(None)))
    return query.all()


@router.post("", response_model=Promotion, status_code=201)
def create_promotion(
    payload: PromotionCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PromotionDB:
    require_role(current_user, *ROLES_PROMOTION_CREATION)
    assert_boutique_access(current_user, payload.boutique_id)
    p = PromotionDB(
        id=str(uuid.uuid4())[:8], nom=payload.nom, boutique_id=payload.boutique_id, secteur=payload.secteur,
        origine=OriginePromotion.gerant, impact_estime=payload.impact_estime, statut=StatutPromotion.en_attente_validation,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.put("/{promotion_id}/statut", response_model=Promotion)
def modifier_statut_promotion(
    promotion_id: str,
    payload: PromotionStatutUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PromotionDB:
    p = db.get(PromotionDB, promotion_id)
    if not p:
        raise HTTPException(status_code=404, detail="Promotion introuvable")
    # Validation/refus d'une promotion = décision siège (cf. CDC : statut initial "en_attente_validation").
    require_role(current_user, *ROLES_PORTEE_RESEAU)
    p.statut = payload.statut
    db.commit()
    db.refresh(p)
    return p
