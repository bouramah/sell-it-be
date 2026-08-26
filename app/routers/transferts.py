import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import a_portee_reseau, boutiques_autorisees, require_permission, require_separation_des_taches
from app.core.database import get_db
from app.core.module_actions import TRANSFERT_DEMANDE, TRANSFERT_RECEPTION, TRANSFERT_VALIDATION
from app.core.security import get_current_user
from app.db_models.models import LigneTransfertStockDB, MouvementStockDB, ProduitDB, StockBoutiqueDB, TransfertStockDB, UtilisateurDB
from app.models.schemas import LigneTransfertStock, MotifMouvementStock, StatutTransfert, TransfertStock
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


def _serialiser_transfert(db: Session, t: TransfertStockDB) -> TransfertStock:
    produits = {p.id: p for p in db.query(ProduitDB).filter(ProduitDB.id.in_({l.produit_id for l in t.lignes})).all()}
    return TransfertStock(
        id=t.id, boutique_source_id=t.boutique_source_id, boutique_destination_id=t.boutique_destination_id,
        demandeur=t.demandeur, statut=t.statut,
        lignes=[
            LigneTransfertStock(
                id=l.id, produit_id=l.produit_id,
                produit_nom=produits[l.produit_id].nom if l.produit_id in produits else l.produit_id,
                quantite=l.quantite, quantite_recue=l.quantite_recue, motif_ecart=l.motif_ecart,
            )
            for l in t.lignes
        ],
    )


@router.get("", response_model=list[TransfertStock])
def list_transferts(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[TransfertStock]:
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
    return [_serialiser_transfert(db, t) for t in query.all()]


@router.post("", response_model=TransfertStock, status_code=201)
def create_transfert(
    payload: TransfertCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> TransfertStock:
    require_permission(db, current_user, TRANSFERT_DEMANDE)
    _assert_transfert_access(current_user, payload.boutique_source_id, payload.boutique_destination_id)
    if not payload.lignes:
        raise HTTPException(status_code=400, detail="Le transfert doit contenir au moins un produit")
    for l in payload.lignes:
        if l.quantite <= 0:
            raise HTTPException(status_code=400, detail="La quantité doit être positive pour chaque produit")

    auteur = f"{current_user.prenom} {current_user.nom}"
    t = TransfertStockDB(
        id=str(uuid.uuid4())[:8], boutique_source_id=payload.boutique_source_id,
        boutique_destination_id=payload.boutique_destination_id, demandeur=payload.demandeur,
        statut=StatutTransfert.demande, created_by=auteur, updated_by=auteur,
    )
    db.add(t)
    for l in payload.lignes:
        db.add(LigneTransfertStockDB(
            id=str(uuid.uuid4())[:8], transfert_id=t.id, produit_id=l.produit_id, quantite=l.quantite,
            created_by=auteur, updated_by=auteur,
        ))
    db.commit()
    db.refresh(t)
    return _serialiser_transfert(db, t)


@router.put("/{transfert_id}/statut", response_model=TransfertStock)
def update_statut(
    transfert_id: str,
    payload: TransfertStatutUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> TransfertStock:
    t = db.get(TransfertStockDB, transfert_id)
    if not t:
        raise HTTPException(status_code=404, detail="Transfert introuvable")
    _assert_transfert_access(current_user, t.boutique_source_id, t.boutique_destination_id)

    if payload.statut == StatutTransfert.recu:
        require_permission(db, current_user, TRANSFERT_RECEPTION)
        if t.statut != StatutTransfert.recu:
            reception_par_produit = {l.produit_id: l for l in (payload.lignes or [])}
            auteur = f"{current_user.prenom} {current_user.nom}"
            for ligne in t.lignes:
                reception = reception_par_produit.get(ligne.produit_id)
                quantite_recue = reception.quantite_recue if reception and reception.quantite_recue is not None else ligne.quantite
                if quantite_recue < 0 or quantite_recue > ligne.quantite:
                    raise HTTPException(status_code=400, detail=f"La quantité reçue pour {ligne.produit_id} doit être comprise entre 0 et {ligne.quantite}")
                motif_ecart = reception.motif_ecart if reception else None
                if quantite_recue < ligne.quantite and not motif_ecart:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Motif obligatoire pour {ligne.produit_id} : seulement {quantite_recue}/{ligne.quantite} reçus (casse, perte en transit…)",
                    )
                _appliquer_reception(db, t, ligne, quantite_recue, auteur)
                ligne.quantite_recue = quantite_recue
                ligne.motif_ecart = motif_ecart if quantite_recue < ligne.quantite else None
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
            db, f"Transfert de stock reçu — #{t.id} ({len(t.lignes)} produit(s))",
            f"{current_user.prenom} {current_user.nom}", t.boutique_destination_id,
            valeur_avant={"statut": ancien_statut}, valeur_apres={
                "statut": t.statut,
                "lignes": [{"produit_id": l.produit_id, "quantite_recue": l.quantite_recue, "motif_ecart": l.motif_ecart} for l in t.lignes],
            },
        )
    db.commit()
    db.refresh(t)

    if payload.statut == StatutTransfert.recu:
        produits = {p.id: p for p in db.query(ProduitDB).filter(ProduitDB.id.in_({l.produit_id for l in t.lignes})).all()}
        detail = ", ".join(f"{l.quantite} x {produits[l.produit_id].nom if l.produit_id in produits else l.produit_id}" for l in t.lignes)
        notifier_gerants_boutique(
            db, t.boutique_destination_id,
            f"Transfert de stock reçu à {nom_boutique(db, t.boutique_destination_id)} : "
            f"{detail} en provenance de {nom_boutique(db, t.boutique_source_id)}. — KFSTORE",
        )

    return _serialiser_transfert(db, t)


def _appliquer_reception(db: Session, t: TransfertStockDB, ligne: LigneTransfertStockDB, quantite_recue: int, auteur: str) -> None:
    """La source perd toujours la quantité expédiée (elle a réellement quitté le stock) ; la
    destination ne gagne que ce qui est réellement arrivé — l'écart (casse/perte en transit,
    CDC 3.9) reste documenté sur la ligne elle-même (quantite_recue/motif_ecart) plutôt que
    comme un mouvement de stock fantôme côté destination."""
    now = datetime.now(timezone.utc)

    source = db.get(StockBoutiqueDB, (t.boutique_source_id, ligne.produit_id))
    if not source or source.quantite_disponible < ligne.quantite:
        raise HTTPException(status_code=400, detail=f"Stock source insuffisant pour {ligne.produit_id}")
    source_avant = source.quantite_disponible
    source.quantite_disponible -= ligne.quantite
    source.derniere_mouvement = now
    source.updated_by = auteur
    db.add(MouvementStockDB(
        id=str(uuid.uuid4())[:8], horodatage=now, produit_id=ligne.produit_id, boutique_id=t.boutique_source_id,
        motif=MotifMouvementStock.transfert_sortant, operateur=t.demandeur, quantite=-ligne.quantite,
        stock_avant=source_avant, stock_apres=source.quantite_disponible,
        created_by=auteur, updated_by=auteur,
    ))

    if quantite_recue > 0:
        dest = db.get(StockBoutiqueDB, (t.boutique_destination_id, ligne.produit_id))
        dest_avant = dest.quantite_disponible if dest else 0
        if dest:
            dest.quantite_disponible += quantite_recue
            dest.derniere_mouvement = now
            dest.updated_by = auteur
        else:
            dest = StockBoutiqueDB(
                boutique_id=t.boutique_destination_id, produit_id=ligne.produit_id,
                quantite_disponible=quantite_recue, quantite_reservee=0, seuil_alerte=0, derniere_mouvement=now,
                created_by=auteur, updated_by=auteur,
            )
            db.add(dest)
        db.add(MouvementStockDB(
            id=str(uuid.uuid4())[:8], horodatage=now, produit_id=ligne.produit_id, boutique_id=t.boutique_destination_id,
            motif=MotifMouvementStock.transfert_entrant, operateur=t.demandeur, quantite=quantite_recue,
            stock_avant=dest_avant, stock_apres=dest.quantite_disponible,
            created_by=auteur, updated_by=auteur,
        ))
