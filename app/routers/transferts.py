import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import a_portee_reseau, boutiques_autorisees, require_permission, require_separation_des_taches
from app.core.database import get_db
from app.core.module_actions import TRANSFERT_DEMANDE, TRANSFERT_RECEPTION, TRANSFERT_VALIDATION
from app.core.security import get_current_user
from app.db_models.models import MouvementStockDB, ProduitDB, StockBoutiqueDB, TransfertStockDB, UtilisateurDB
from app.models.schemas import MotifMouvementStock, StatutTransfert, TransfertStock
from app.models.write_schemas import TransfertCreate, TransfertStatutUpdate
from app.services.audit import log_audit
from app.services.notifications import nom_boutique, notifier_gerants_boutique

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
    auteur = f"{current_user.prenom} {current_user.nom}"
    t = TransfertStockDB(id=str(uuid.uuid4())[:8], statut=StatutTransfert.demande, created_by=auteur, updated_by=auteur, **payload.model_dump())
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
            quantite_recue = payload.quantite_recue if payload.quantite_recue is not None else t.quantite
            if quantite_recue < 0 or quantite_recue > t.quantite:
                raise HTTPException(status_code=400, detail=f"La quantité reçue doit être comprise entre 0 et {t.quantite}")
            if quantite_recue < t.quantite and not payload.motif_ecart:
                raise HTTPException(
                    status_code=400,
                    detail=f"Motif obligatoire : seulement {quantite_recue}/{t.quantite} reçus (casse, perte en transit…)",
                )
            _appliquer_reception(db, t, quantite_recue, f"{current_user.prenom} {current_user.nom}")
            t.quantite_recue = quantite_recue
            t.motif_ecart = payload.motif_ecart if quantite_recue < t.quantite else None
    else:
        require_permission(db, current_user, TRANSFERT_VALIDATION)
        if payload.statut == StatutTransfert.valide:
            require_separation_des_taches(db, current_user, t.created_by)

    ancien_statut = t.statut
    t.statut = payload.statut
    t.updated_by = f"{current_user.prenom} {current_user.nom}"
    if payload.statut == StatutTransfert.valide:
        log_audit(
            db, f"Transfert de stock validé — #{t.id}", f"{current_user.prenom} {current_user.nom}",
            t.boutique_destination_id,
            valeur_avant={"statut": ancien_statut}, valeur_apres={"statut": t.statut},
        )
    elif payload.statut == StatutTransfert.recu:
        log_audit(
            db, f"Transfert de stock reçu — #{t.id} ({t.quantite_recue}/{t.quantite})",
            f"{current_user.prenom} {current_user.nom}", t.boutique_destination_id,
            valeur_avant={"statut": ancien_statut}, valeur_apres={"statut": t.statut, "quantite_recue": t.quantite_recue, "motif_ecart": t.motif_ecart},
        )
    db.commit()
    db.refresh(t)

    if payload.statut == StatutTransfert.recu:
        produit = db.get(ProduitDB, t.produit_id)
        notifier_gerants_boutique(
            db, t.boutique_destination_id,
            f"Transfert de stock reçu à {nom_boutique(db, t.boutique_destination_id)} : "
            f"{t.quantite} x {produit.nom if produit else t.produit_id} en provenance de "
            f"{nom_boutique(db, t.boutique_source_id)}. — KFSTORE",
        )

    return t


def _appliquer_reception(db: Session, t: TransfertStockDB, quantite_recue: int, auteur: str) -> None:
    """La source perd toujours la quantité expédiée (elle a réellement quitté le stock) ; la
    destination ne gagne que ce qui est réellement arrivé — l'écart (casse/perte en transit,
    CDC 3.9) reste documenté sur le transfert lui-même (quantite_recue/motif_ecart) plutôt que
    comme un mouvement de stock fantôme côté destination."""
    now = datetime.now(timezone.utc)

    source = db.get(StockBoutiqueDB, (t.boutique_source_id, t.produit_id))
    if not source or source.quantite_disponible < t.quantite:
        raise HTTPException(status_code=400, detail="Stock source insuffisant pour ce transfert")
    source.quantite_disponible -= t.quantite
    source.derniere_mouvement = now
    source.updated_by = auteur
    db.add(MouvementStockDB(
        id=str(uuid.uuid4())[:8], horodatage=now, produit_id=t.produit_id, boutique_id=t.boutique_source_id,
        motif=MotifMouvementStock.transfert_sortant, operateur=t.demandeur, quantite=-t.quantite,
        created_by=auteur, updated_by=auteur,
    ))

    if quantite_recue > 0:
        dest = db.get(StockBoutiqueDB, (t.boutique_destination_id, t.produit_id))
        if dest:
            dest.quantite_disponible += quantite_recue
            dest.derniere_mouvement = now
            dest.updated_by = auteur
        else:
            db.add(StockBoutiqueDB(
                boutique_id=t.boutique_destination_id, produit_id=t.produit_id,
                quantite_disponible=quantite_recue, quantite_reservee=0, seuil_alerte=0, derniere_mouvement=now,
                created_by=auteur, updated_by=auteur,
            ))
        db.add(MouvementStockDB(
            id=str(uuid.uuid4())[:8], horodatage=now, produit_id=t.produit_id, boutique_id=t.boutique_destination_id,
            motif=MotifMouvementStock.transfert_entrant, operateur=t.demandeur, quantite=quantite_recue,
            created_by=auteur, updated_by=auteur,
        ))
