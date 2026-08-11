import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import apply_boutique_filter, assert_boutique_access, require_role
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import EcartInventaireDB, MouvementStockDB, ProduitDB, StockBoutiqueDB, UtilisateurDB
from app.models.schemas import MotifMouvementStock, Role, StatutEcartInventaire
from app.models.write_schemas import EcartInventaireCreate, MouvementStockCreate, StockLigneCreate, StockLigneUpdate

router = APIRouter(prefix="/api/v1/stock", tags=["stock"])

# CDC 3.3 : la gestion du stock (ajout de ligne, mouvements manuels, inventaire) relève de la
# supervision de boutique — vendeur/caissier ne font que consulter et vendre (stock décrémenté
# automatiquement par la commande), responsable_achats n'a qu'un accès en lecture sur le stock.
ROLES_STOCK_ECRITURE = (Role.gerant, Role.administrateur)


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


class LigneMouvementStock(BaseModel):
    id: str
    horodatage: str
    produit_id: str
    produit_nom: str
    boutique_id: str
    motif: MotifMouvementStock
    operateur: str
    quantite: int


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
        )
        for s in rows
    ]


@router.post("", response_model=LigneStock, status_code=201)
def create_ligne_stock(
    payload: StockLigneCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LigneStock:
    require_role(current_user, *ROLES_STOCK_ECRITURE)
    assert_boutique_access(current_user, payload.boutique_id)
    produit = db.get(ProduitDB, payload.produit_id)
    if not produit:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    existing = db.get(StockBoutiqueDB, (payload.boutique_id, payload.produit_id))
    if existing:
        raise HTTPException(status_code=409, detail="Ce produit est déjà en stock dans cette boutique")
    s = StockBoutiqueDB(
        boutique_id=payload.boutique_id,
        produit_id=payload.produit_id,
        quantite_disponible=payload.quantite_disponible,
        quantite_reservee=payload.quantite_reservee,
        seuil_alerte=payload.seuil_alerte,
        derniere_mouvement=datetime.now(timezone.utc),
    )
    db.add(s)
    db.commit()
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
    )


@router.put("/{boutique_id}/{produit_id}", response_model=LigneStock)
def update_ligne_stock(
    boutique_id: str,
    produit_id: str,
    payload: StockLigneUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LigneStock:
    require_role(current_user, *ROLES_STOCK_ECRITURE)
    assert_boutique_access(current_user, boutique_id)
    s = db.get(StockBoutiqueDB, (boutique_id, produit_id))
    if not s:
        raise HTTPException(status_code=404, detail="Ligne de stock introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    produit = db.get(ProduitDB, produit_id)
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
    )


@router.delete("/{boutique_id}/{produit_id}", status_code=204)
def delete_ligne_stock(
    boutique_id: str,
    produit_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_role(current_user, *ROLES_STOCK_ECRITURE)
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
        )
        for m in rows
    ]


@router.post("/mouvements", response_model=LigneMouvementStock, status_code=201)
def create_mouvement(
    payload: MouvementStockCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LigneMouvementStock:
    require_role(current_user, *ROLES_STOCK_ECRITURE)
    assert_boutique_access(current_user, payload.boutique_id)
    produit = db.get(ProduitDB, payload.produit_id)
    if not produit:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    now = datetime.now(timezone.utc)
    mouvement = MouvementStockDB(
        id=str(uuid.uuid4())[:8],
        horodatage=now,
        produit_id=payload.produit_id,
        boutique_id=payload.boutique_id,
        motif=payload.motif,
        operateur=payload.operateur,
        quantite=payload.quantite,
    )
    db.add(mouvement)

    ligne = db.get(StockBoutiqueDB, (payload.boutique_id, payload.produit_id))
    if ligne:
        ligne.quantite_disponible += payload.quantite
        ligne.derniere_mouvement = now
    else:
        ligne = StockBoutiqueDB(
            boutique_id=payload.boutique_id,
            produit_id=payload.produit_id,
            quantite_disponible=max(payload.quantite, 0),
            quantite_reservee=0,
            seuil_alerte=0,
            derniere_mouvement=now,
        )
        db.add(ligne)

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
    require_role(current_user, *ROLES_STOCK_ECRITURE)
    assert_boutique_access(current_user, payload.boutique_id)
    produit = db.get(ProduitDB, payload.produit_id)
    if not produit:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    statut = StatutEcartInventaire.conforme if payload.theorique == payload.reel else StatutEcartInventaire.a_investiguer
    e = EcartInventaireDB(id=str(uuid.uuid4())[:8], statut=statut, **payload.model_dump())
    db.add(e)
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
