import uuid
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import (
    CommandeClientDB,
    CommandeFournisseurDB,
    FournisseurDB,
    LigneCommandeClientDB,
    LigneCommandeFournisseurDB,
    MouvementStockDB,
    PaiementClientDB,
    PaiementFournisseurDB,
    ProduitDB,
    StockBoutiqueDB,
)
from app.models.schemas import (
    ArticleCommande,
    ArticleCommandeFournisseur,
    CommandeClient,
    CommandeClientDetail,
    CommandeFournisseurDetail,
    LigneCommandeFournisseur,
    ModePaiement,
    MotifMouvementStock,
    StatutCommandeFournisseur,
    StatutPaiement,
)
from app.models.write_schemas import (
    CommandeClientCreate,
    CommandeClientUpdate,
    CommandeFournisseurCreate,
    CommandeFournisseurUpdate,
    ReceptionCreate,
)

router = APIRouter(prefix="/api/v1", tags=["commandes"])


def _produits_by_id(db: Session, ids: set[str]) -> dict[str, ProduitDB]:
    produits = {p.id: p for p in db.query(ProduitDB).filter(ProduitDB.id.in_(ids)).all()}
    manquants = ids - produits.keys()
    if manquants:
        raise HTTPException(status_code=404, detail=f"Produit(s) introuvable(s) : {', '.join(manquants)}")
    return produits


@router.get("/commandes-clients", response_model=list[CommandeClient])
def list_commandes_clients(boutique_id: str | None = None, db: Session = Depends(get_db)) -> list[CommandeClientDB]:
    query = db.query(CommandeClientDB)
    if boutique_id:
        query = query.filter(CommandeClientDB.boutique_id == boutique_id)
    return query.all()


@router.get("/commandes-clients/{commande_id}", response_model=CommandeClientDetail)
def get_commande_client(commande_id: str, db: Session = Depends(get_db)) -> CommandeClientDetail:
    c = db.get(CommandeClientDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    produits = _produits_by_id(db, {l.produit_id for l in c.lignes}) if c.lignes else {}
    return CommandeClientDetail(
        id=c.id, client_nom=c.client_nom, boutique_id=c.boutique_id, canal=c.canal,
        mode_paiement=c.mode_paiement, montant=c.montant, statut=c.statut, date_creation=c.date_creation,
        articles=[
            ArticleCommande(id=l.id, produit_id=l.produit_id, produit_nom=produits[l.produit_id].nom, quantite=l.quantite, prix_unitaire=l.prix_unitaire)
            for l in c.lignes
        ],
    )


@router.post("/commandes-clients", response_model=CommandeClientDetail, status_code=201)
def create_commande_client(
    payload: CommandeClientCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> CommandeClientDetail:
    if not payload.articles:
        raise HTTPException(status_code=400, detail="La commande doit contenir au moins un article")
    produits = _produits_by_id(db, {a.produit_id for a in payload.articles})

    c = CommandeClientDB(
        id=str(uuid.uuid4())[:8], client_nom=payload.client_nom, boutique_id=payload.boutique_id,
        canal=payload.canal, mode_paiement=payload.mode_paiement, statut=payload.statut, montant=0.0,
    )
    db.add(c)
    montant = 0.0
    for a in payload.articles:
        prix = a.prix_unitaire if a.prix_unitaire is not None else produits[a.produit_id].prix
        montant += a.quantite * prix
        db.add(LigneCommandeClientDB(id=str(uuid.uuid4())[:8], commande_id=c.id, produit_id=a.produit_id, quantite=a.quantite, prix_unitaire=prix))
    c.montant = montant

    if payload.mode_paiement != ModePaiement.credit_client:
        statut_paiement = StatutPaiement.en_attente if payload.mode_paiement == ModePaiement.a_la_livraison else StatutPaiement.encaisse
        db.add(PaiementClientDB(
            id=str(uuid.uuid4())[:8], client_nom=c.client_nom, reference=f"#{c.id}", boutique_id=c.boutique_id,
            mode_paiement=payload.mode_paiement, date=date.today(), montant=montant, statut=statut_paiement,
        ))

    db.commit()
    return get_commande_client(c.id, db)


@router.put("/commandes-clients/{commande_id}", response_model=CommandeClient)
def update_commande_client(
    commande_id: str,
    payload: CommandeClientUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> CommandeClientDB:
    c = db.get(CommandeClientDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return c


@router.get("/commandes-fournisseurs", response_model=list[LigneCommandeFournisseur])
def list_commandes_fournisseurs(boutique_id: str | None = None, db: Session = Depends(get_db)) -> list[CommandeFournisseurDB]:
    query = db.query(CommandeFournisseurDB)
    if boutique_id:
        query = query.filter(CommandeFournisseurDB.boutique_id == boutique_id)
    return query.all()


@router.get("/commandes-fournisseurs/{commande_id}", response_model=CommandeFournisseurDetail)
def get_commande_fournisseur(commande_id: str, db: Session = Depends(get_db)) -> CommandeFournisseurDetail:
    c = db.get(CommandeFournisseurDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    produits = _produits_by_id(db, {l.produit_id for l in c.lignes}) if c.lignes else {}
    return CommandeFournisseurDetail(
        id=c.id, fournisseur_id=c.fournisseur_id, boutique_id=c.boutique_id,
        date_attendue=c.date_attendue, montant=c.montant, statut=c.statut, date_reception=c.date_reception,
        articles=[
            ArticleCommandeFournisseur(
                id=l.id, produit_id=l.produit_id, produit_nom=produits[l.produit_id].nom,
                quantite=l.quantite, prix_unitaire=l.prix_unitaire, quantite_recue=l.quantite_recue,
            )
            for l in c.lignes
        ],
    )


@router.post("/commandes-fournisseurs", response_model=CommandeFournisseurDetail, status_code=201)
def create_commande_fournisseur(
    payload: CommandeFournisseurCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> CommandeFournisseurDetail:
    if not payload.articles:
        raise HTTPException(status_code=400, detail="La commande doit contenir au moins un article")
    produits = _produits_by_id(db, {a.produit_id for a in payload.articles})

    c = CommandeFournisseurDB(
        id=str(uuid.uuid4())[:8], fournisseur_id=payload.fournisseur_id, boutique_id=payload.boutique_id,
        date_attendue=payload.date_attendue, statut=payload.statut, montant=0.0,
    )
    db.add(c)
    montant = 0.0
    for a in payload.articles:
        prix = a.prix_unitaire if a.prix_unitaire is not None else produits[a.produit_id].prix
        montant += a.quantite * prix
        db.add(LigneCommandeFournisseurDB(id=str(uuid.uuid4())[:8], commande_id=c.id, produit_id=a.produit_id, quantite=a.quantite, prix_unitaire=prix, quantite_recue=0))
    c.montant = montant
    db.commit()
    return get_commande_fournisseur(c.id, db)


@router.put("/commandes-fournisseurs/{commande_id}", response_model=LigneCommandeFournisseur)
def update_commande_fournisseur(
    commande_id: str,
    payload: CommandeFournisseurUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> CommandeFournisseurDB:
    c = db.get(CommandeFournisseurDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return c


@router.post("/commandes-fournisseurs/{commande_id}/reception", response_model=CommandeFournisseurDetail)
def receptionner_commande_fournisseur(
    commande_id: str,
    payload: ReceptionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> CommandeFournisseurDetail:
    c = db.get(CommandeFournisseurDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    if not payload.lignes:
        raise HTTPException(status_code=400, detail="Aucune ligne à réceptionner")

    lignes_by_produit = {l.produit_id: l for l in c.lignes}
    for r in payload.lignes:
        ligne = lignes_by_produit.get(r.produit_id)
        if not ligne:
            raise HTTPException(status_code=400, detail=f"Produit {r.produit_id} absent de la commande")
        if r.quantite <= 0:
            raise HTTPException(status_code=400, detail="La quantité reçue doit être positive")
        restant = ligne.quantite - ligne.quantite_recue
        if r.quantite > restant:
            raise HTTPException(status_code=400, detail=f"Quantité reçue supérieure au reliquat pour {r.produit_id} ({restant} restant)")

    now = datetime.now(timezone.utc)
    for r in payload.lignes:
        ligne = lignes_by_produit[r.produit_id]
        ligne.quantite_recue += r.quantite

        stock = db.get(StockBoutiqueDB, (c.boutique_id, r.produit_id))
        if stock:
            stock.quantite_disponible += r.quantite
            stock.derniere_mouvement = now
        else:
            db.add(StockBoutiqueDB(
                boutique_id=c.boutique_id, produit_id=r.produit_id,
                quantite_disponible=r.quantite, quantite_reservee=0, seuil_alerte=0, derniere_mouvement=now,
            ))
        db.add(MouvementStockDB(
            id=str(uuid.uuid4())[:8], horodatage=now, produit_id=r.produit_id, boutique_id=c.boutique_id,
            motif=MotifMouvementStock.achat_reception_fournisseur, operateur=payload.operateur, quantite=r.quantite,
        ))

    if all(l.quantite_recue >= l.quantite for l in c.lignes):
        c.statut = StatutCommandeFournisseur.receptionnee
        c.date_reception = date.today()
        fournisseur = db.get(FournisseurDB, c.fournisseur_id)
        db.add(PaiementFournisseurDB(
            id=str(uuid.uuid4())[:8], fournisseur_nom=fournisseur.nom if fournisseur else c.fournisseur_id,
            reference=f"#{c.id}", boutique_id=c.boutique_id, mode_paiement=ModePaiement.virement,
            date=date.today(), montant=c.montant, statut=StatutPaiement.en_attente,
        ))
    else:
        c.statut = StatutCommandeFournisseur.receptionnee_partielle

    db.commit()
    return get_commande_fournisseur(commande_id, db)
