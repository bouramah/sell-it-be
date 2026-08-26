import uuid
from datetime import date, datetime, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import apply_boutique_filter, assert_boutique_access, require_permission
from app.core.database import get_db
from app.core.module_actions import STOCK_ECRITURE
from app.core.security import get_current_user
from app.db_models.models import EcartInventaireDB, MouvementStockDB, ProduitDB, StockBoutiqueDB, UtilisateurDB
from app.models.schemas import MotifMouvementStock, PalierPrix, StatutEcartInventaire
from app.models.write_schemas import EcartInventaireCreate, MouvementStockCreate, StockLigneCreate, StockLigneUpdate
from app.services.audit import log_audit
from app.services.pricing import prix_effectif_a_date, prix_effectifs_batch, resoudre_prix

router = APIRouter(prefix="/api/v1/stock", tags=["stock"])


class LigneStock(BaseModel):
    boutique_id: str
    produit_id: str
    produit_nom: str
    secteur: str
    quantite_disponible: int
    quantite_reservee: int
    seuil_alerte: int
    statut: str
    derniere_mouvement: str
    # Prix effectifs pour cette boutique — surcharge boutique si définie, sinon prix réseau du produit.
    prix_detail: float
    prix_semi_gros: float
    prix_gros: float


class LigneMouvementStock(BaseModel):
    id: str
    horodatage: str
    produit_id: str
    produit_nom: str
    boutique_id: str
    motif: MotifMouvementStock
    operateur: str
    quantite: int
    stock_avant: int
    stock_apres: int


class LigneEcartInventaire(BaseModel):
    id: str
    produit_id: str
    produit_nom: str
    boutique_id: str
    theorique: int
    reel: int
    ecart: int
    statut: StatutEcartInventaire


def _statut_stock(disponible: int, seuil: int) -> str:
    if disponible <= seuil * 0.5:
        return "critique"
    if disponible <= seuil:
        return "a_surveiller"
    return "correct"


@router.get("", response_model=list[LigneStock])
def list_stock(
    boutique_id: str | None = None,
    secteur: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[LigneStock]:
    produits_by_id = {p.id: p for p in db.query(ProduitDB).all()}
    query = apply_boutique_filter(db.query(StockBoutiqueDB), StockBoutiqueDB.boutique_id, current_user, boutique_id)
    rows = query.all()
    if secteur:
        rows = [s for s in rows if produits_by_id[s.produit_id].secteur == secteur]
    today = date.today()
    cache = prix_effectifs_batch(db, {s.boutique_id for s in rows}, {s.produit_id for s in rows}, today)
    return [
        LigneStock(
            boutique_id=s.boutique_id,
            produit_id=s.produit_id,
            produit_nom=produits_by_id[s.produit_id].nom,
            secteur=produits_by_id[s.produit_id].secteur,
            quantite_disponible=s.quantite_disponible,
            quantite_reservee=s.quantite_reservee,
            seuil_alerte=s.seuil_alerte,
            statut=_statut_stock(s.quantite_disponible, s.seuil_alerte),
            derniere_mouvement=s.derniere_mouvement.isoformat(),
            prix_detail=resoudre_prix(cache, s.boutique_id, s.produit_id, PalierPrix.detail) or 0.0,
            prix_semi_gros=resoudre_prix(cache, s.boutique_id, s.produit_id, PalierPrix.semi_gros) or 0.0,
            prix_gros=resoudre_prix(cache, s.boutique_id, s.produit_id, PalierPrix.gros) or 0.0,
        )
        for s in rows
    ]


@router.post("", response_model=LigneStock, status_code=201)
def create_ligne_stock(
    payload: StockLigneCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LigneStock:
    require_permission(db, current_user, STOCK_ECRITURE)
    assert_boutique_access(current_user, payload.boutique_id)
    produit = db.get(ProduitDB, payload.produit_id)
    if not produit:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    existing = db.get(StockBoutiqueDB, (payload.boutique_id, payload.produit_id))
    if existing:
        raise HTTPException(status_code=409, detail="Ce produit est déjà en stock dans cette boutique")
    auteur = f"{current_user.prenom} {current_user.nom}"
    s = StockBoutiqueDB(
        boutique_id=payload.boutique_id,
        produit_id=payload.produit_id,
        quantite_disponible=payload.quantite_disponible,
        quantite_reservee=payload.quantite_reservee,
        seuil_alerte=payload.seuil_alerte,
        derniere_mouvement=datetime.now(timezone.utc),
        created_by=auteur,
        updated_by=auteur,
    )
    db.add(s)
    db.commit()
    today = date.today()
    return LigneStock(
        boutique_id=s.boutique_id,
        produit_id=s.produit_id,
        produit_nom=produit.nom,
        secteur=produit.secteur,
        quantite_disponible=s.quantite_disponible,
        quantite_reservee=s.quantite_reservee,
        seuil_alerte=s.seuil_alerte,
        statut=_statut_stock(s.quantite_disponible, s.seuil_alerte),
        derniere_mouvement=s.derniere_mouvement.isoformat(),
        prix_detail=prix_effectif_a_date(db, produit.id, s.boutique_id, PalierPrix.detail, today) or 0.0,
        prix_semi_gros=prix_effectif_a_date(db, produit.id, s.boutique_id, PalierPrix.semi_gros, today) or 0.0,
        prix_gros=prix_effectif_a_date(db, produit.id, s.boutique_id, PalierPrix.gros, today) or 0.0,
    )


@router.put("/{boutique_id}/{produit_id}", response_model=LigneStock)
def update_ligne_stock(
    boutique_id: str,
    produit_id: str,
    payload: StockLigneUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LigneStock:
    require_permission(db, current_user, STOCK_ECRITURE)
    assert_boutique_access(current_user, boutique_id)
    s = db.get(StockBoutiqueDB, (boutique_id, produit_id))
    if not s:
        raise HTTPException(status_code=404, detail="Ligne de stock introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    s.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    produit = db.get(ProduitDB, produit_id)
    today = date.today()
    return LigneStock(
        boutique_id=s.boutique_id,
        produit_id=s.produit_id,
        produit_nom=produit.nom,
        secteur=produit.secteur,
        quantite_disponible=s.quantite_disponible,
        quantite_reservee=s.quantite_reservee,
        seuil_alerte=s.seuil_alerte,
        statut=_statut_stock(s.quantite_disponible, s.seuil_alerte),
        derniere_mouvement=s.derniere_mouvement.isoformat(),
        prix_detail=prix_effectif_a_date(db, produit_id, boutique_id, PalierPrix.detail, today) or 0.0,
        prix_semi_gros=prix_effectif_a_date(db, produit_id, boutique_id, PalierPrix.semi_gros, today) or 0.0,
        prix_gros=prix_effectif_a_date(db, produit_id, boutique_id, PalierPrix.gros, today) or 0.0,
    )


@router.delete("/{boutique_id}/{produit_id}", status_code=204)
def delete_ligne_stock(
    boutique_id: str,
    produit_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, STOCK_ECRITURE)
    assert_boutique_access(current_user, boutique_id)
    s = db.get(StockBoutiqueDB, (boutique_id, produit_id))
    if not s:
        raise HTTPException(status_code=404, detail="Ligne de stock introuvable")
    db.delete(s)
    db.commit()


@router.get("/mouvements", response_model=list[LigneMouvementStock])
def list_mouvements(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[LigneMouvementStock]:
    produits_by_id = {p.id: p for p in db.query(ProduitDB).all()}
    query = apply_boutique_filter(db.query(MouvementStockDB), MouvementStockDB.boutique_id, current_user, boutique_id)
    rows = sorted(query.all(), key=lambda m: m.horodatage, reverse=True)
    return [
        LigneMouvementStock(
            id=m.id,
            horodatage=m.horodatage.isoformat(),
            produit_id=m.produit_id,
            produit_nom=produits_by_id[m.produit_id].nom,
            boutique_id=m.boutique_id,
            motif=m.motif,
            operateur=m.operateur,
            quantite=m.quantite,
            stock_avant=m.stock_avant,
            stock_apres=m.stock_apres,
        )
        for m in rows
    ]


@router.post("/mouvements", response_model=LigneMouvementStock, status_code=201)
def create_mouvement(
    payload: MouvementStockCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LigneMouvementStock:
    require_permission(db, current_user, STOCK_ECRITURE)
    assert_boutique_access(current_user, payload.boutique_id)
    produit = db.get(ProduitDB, payload.produit_id)
    if not produit:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    auteur = f"{current_user.prenom} {current_user.nom}"
    now = datetime.now(timezone.utc)

    ligne = db.get(StockBoutiqueDB, (payload.boutique_id, payload.produit_id))
    stock_avant = ligne.quantite_disponible if ligne else 0
    stock_apres = stock_avant + payload.quantite if ligne else max(payload.quantite, 0)

    mouvement = MouvementStockDB(
        id=str(uuid.uuid4())[:8],
        horodatage=now,
        produit_id=payload.produit_id,
        boutique_id=payload.boutique_id,
        motif=payload.motif,
        operateur=payload.operateur,
        quantite=payload.quantite,
        stock_avant=stock_avant,
        stock_apres=stock_apres,
        created_by=auteur,
        updated_by=auteur,
    )
    db.add(mouvement)

    if ligne:
        ligne.quantite_disponible = stock_apres
        ligne.derniere_mouvement = now
        ligne.updated_by = auteur
    else:
        ligne = StockBoutiqueDB(
            boutique_id=payload.boutique_id,
            produit_id=payload.produit_id,
            quantite_disponible=stock_apres,
            quantite_reservee=0,
            seuil_alerte=0,
            derniere_mouvement=now,
            created_by=auteur,
            updated_by=auteur,
        )
        db.add(ligne)

    log_audit(
        db, f"Mouvement de stock — {produit.nom} ({payload.motif.value}, {payload.quantite:+d})", auteur,
        payload.boutique_id, valeur_apres={"motif": payload.motif.value, "quantite": payload.quantite, "produit_id": payload.produit_id},
    )
    db.commit()
    return LigneMouvementStock(
        id=mouvement.id,
        horodatage=mouvement.horodatage.isoformat(),
        produit_id=mouvement.produit_id,
        produit_nom=produit.nom,
        boutique_id=mouvement.boutique_id,
        motif=mouvement.motif,
        operateur=mouvement.operateur,
        quantite=mouvement.quantite,
        stock_avant=mouvement.stock_avant,
        stock_apres=mouvement.stock_apres,
    )


@router.get("/inventaire", response_model=list[LigneEcartInventaire])
def list_inventaire(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[LigneEcartInventaire]:
    produits_by_id = {p.id: p for p in db.query(ProduitDB).all()}
    query = apply_boutique_filter(db.query(EcartInventaireDB), EcartInventaireDB.boutique_id, current_user, boutique_id)
    return [
        LigneEcartInventaire(
            id=e.id,
            produit_id=e.produit_id,
            produit_nom=produits_by_id[e.produit_id].nom,
            boutique_id=e.boutique_id,
            theorique=e.theorique,
            reel=e.reel,
            ecart=e.reel - e.theorique,
            statut=e.statut,
        )
        for e in query.all()
    ]


@router.post("/inventaire", response_model=LigneEcartInventaire, status_code=201)
def create_inventaire(
    payload: EcartInventaireCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LigneEcartInventaire:
    require_permission(db, current_user, STOCK_ECRITURE)
    assert_boutique_access(current_user, payload.boutique_id)
    produit = db.get(ProduitDB, payload.produit_id)
    if not produit:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    statut = StatutEcartInventaire.conforme if payload.theorique == payload.reel else StatutEcartInventaire.a_investiguer
    auteur = f"{current_user.prenom} {current_user.nom}"
    e = EcartInventaireDB(id=str(uuid.uuid4())[:8], statut=statut, created_by=auteur, updated_by=auteur, **payload.model_dump())
    db.add(e)
    if statut == StatutEcartInventaire.a_investiguer:
        log_audit(
            db, f"Écart d'inventaire — {produit.nom} (théorique {payload.theorique}, réel {payload.reel})", auteur,
            payload.boutique_id, valeur_apres={"theorique": payload.theorique, "reel": payload.reel, "ecart": payload.reel - payload.theorique},
        )
    db.commit()
    return LigneEcartInventaire(
        id=e.id,
        produit_id=e.produit_id,
        produit_nom=produit.nom,
        boutique_id=e.boutique_id,
        theorique=e.theorique,
        reel=e.reel,
        ecart=e.reel - e.theorique,
        statut=e.statut,
    )
