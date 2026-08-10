import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import MouvementStockDB, StockBoutiqueDB, TransfertStockDB
from app.models.schemas import MotifMouvementStock, StatutTransfert, TransfertStock
from app.models.write_schemas import TransfertCreate, TransfertStatutUpdate

router = APIRouter(prefix="/api/v1/transferts", tags=["transferts"])


@router.get("", response_model=list[TransfertStock])
def list_transferts(boutique_id: str | None = None, db: Session = Depends(get_db)) -> list[TransfertStockDB]:
    query = db.query(TransfertStockDB)
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
    current_user=Depends(get_current_user),
) -> TransfertStockDB:
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
    current_user=Depends(get_current_user),
) -> TransfertStockDB:
    t = db.get(TransfertStockDB, transfert_id)
    if not t:
        raise HTTPException(status_code=404, detail="Transfert introuvable")

    if payload.statut == StatutTransfert.recu and t.statut != StatutTransfert.recu:
        _appliquer_reception(db, t)

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
