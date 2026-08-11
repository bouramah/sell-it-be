import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import a_portee_reseau, assert_boutique_access, boutiques_autorisees, require_permission
from app.core.database import get_db
from app.core.module_actions import PROMOTION_CREATION, PROMOTION_VALIDATION
from app.core.security import get_current_user
from app.db_models.models import PromotionDB, UtilisateurDB
from app.models.schemas import OriginePromotion, Promotion, StatutPromotion
from app.models.write_schemas import PromotionCreate, PromotionStatutUpdate

router = APIRouter(prefix="/api/v1/promotions", tags=["promotions"])


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
    require_permission(db, current_user, PROMOTION_CREATION)
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
    require_permission(db, current_user, PROMOTION_VALIDATION)
    p.statut = payload.statut
    db.commit()
    db.refresh(p)
    return p
