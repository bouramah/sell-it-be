import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import a_portee_reseau, boutiques_autorisees, require_permission
from app.core.database import get_db
from app.core.module_actions import TRANSFERT_DEMANDE, TRANSFERT_RECEPTION, TRANSFERT_VALIDATION
from app.core.security import get_current_user
from app.db_models.models import MouvementStockDB, StockBoutiqueDB, TransfertStockDB, UtilisateurDB
from app.models.schemas import MotifMouvementStock, StatutTransfert, TransfertStock
from app.models.write_schemas import TransfertCreate, TransfertStatutUpdate

router = APIRouter(prefix="/api/v1/transferts", tags=["transferts"])


def _assert_transfert_access(current_user: UtilisateurDB, boutique_source_id: str, boutique_destination_id: str) -> None:
    if a_portee_reseau(current_user):
        return
    autorisees = boutiques_autorisees(current_user)
    if boutique_source_id not in autorisees and boutique_destination_id not in autorisees:
        raise HTTPException(status_code=403, detail="Vous n'avez pas accès à ce transfert")


@router.get("", response_model=list[TransfertStock])
def list_transferts(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[TransfertStockDB]:
    query = db.query(TransfertStockDB)
    if not a_portee_reseau(current_user):
        autorisees = boutiques_autorisees(current_user)
        query = query.filter(
            (TransfertStockDB.boutique_source_id.in_(autorisees))
            | (TransfertStockDB.boutique_destination_id.in_(autorisees))
        )
    if boutique_id:
        query = query.filter(
            (TransfertStockDB.boutique_source_id == boutique_id)
            | (TransfertStockDB.boutique_destination_id == boutique_id)
        )
    return query.all()


@router.post("", response_model=TransfertStock, status_code=201)
def create_transfert(
    payload: TransfertCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> TransfertStockDB:
    require_permission(db, current_user, TRANSFERT_DEMANDE)
    _assert_transfert_access(current_user, payload.boutique_source_id, payload.boutique_destination_id)
    t = TransfertStockDB(id=str(uuid.uuid4())[:8], statut=StatutTransfert.demande, **payload.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.put("/{transfert_id}/statut", response_model=TransfertStock)
def update_statut(
    transfert_id: str,
    payload: TransfertStatutUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> TransfertStockDB:
    t = db.get(TransfertStockDB, transfert_id)
    if not t:
        raise HTTPException(status_code=404, detail="Transfert introuvable")
    _assert_transfert_access(current_user, t.boutique_source_id, t.boutique_destination_id)

    if payload.statut == StatutTransfert.recu:
        require_permission(db, current_user, TRANSFERT_RECEPTION)
        if t.statut != StatutTransfert.recu:
            _appliquer_reception(db, t)
    else:
        require_permission(db, current_user, TRANSFERT_VALIDATION)

    t.statut = payload.statut
    db.commit()
    db.refresh(t)
    return t


def _appliquer_reception(db: Session, t: TransfertStockDB) -> None:
    now = datetime.now(timezone.utc)

    source = db.get(StockBoutiqueDB, (t.boutique_source_id, t.produit_id))
    if not source or source.quantite_disponible < t.quantite:
        raise HTTPException(status_code=400, detail="Stock source insuffisant pour ce transfert")
    source.quantite_disponible -= t.quantite
    source.derniere_mouvement = now
    db.add(MouvementStockDB(
        id=str(uuid.uuid4())[:8], horodatage=now, produit_id=t.produit_id, boutique_id=t.boutique_source_id,
        motif=MotifMouvementStock.transfert_sortant, operateur=t.demandeur, quantite=-t.quantite,
    ))

    dest = db.get(StockBoutiqueDB, (t.boutique_destination_id, t.produit_id))
    if dest:
        dest.quantite_disponible += t.quantite
        dest.derniere_mouvement = now
    else:
        db.add(StockBoutiqueDB(
            boutique_id=t.boutique_destination_id, produit_id=t.produit_id,
            quantite_disponible=t.quantite, quantite_reservee=0, seuil_alerte=0, derniere_mouvement=now,
        ))
    db.add(MouvementStockDB(
        id=str(uuid.uuid4())[:8], horodatage=now, produit_id=t.produit_id, boutique_id=t.boutique_destination_id,
        motif=MotifMouvementStock.transfert_entrant, operateur=t.demandeur, quantite=t.quantite,
    ))
