import uuid
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import apply_boutique_filter, assert_boutique_access, require_permission
from app.core.database import get_db
from app.core.module_actions import COMMANDE_CLIENT, COMMANDE_FOURNISSEUR_CREATION, COMMANDE_FOURNISSEUR_RECEPTION
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
    UtilisateurDB,
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
    StatutCommandeClient,
    StatutCommandeFournisseur,
    StatutPaiement,
)
from app.models.write_schemas import (
    CommandeClientCreate,
    CommandeClientUpdate,
    CommandeFournisseurCreate,
    CommandeFournisseurUpdate,
    CorrectionReceptionCreate,
    ReceptionCreate,
)
from app.services.notifications import nom_boutique, notifier_client, notifier_gerants_boutique

router = APIRouter(prefix="/api/v1", tags=["commandes"])


def _produits_by_id(db: Session, ids: set[str]) -> dict[str, ProduitDB]:
    produits = {p.id: p for p in db.query(ProduitDB).filter(ProduitDB.id.in_(ids)).all()}
    manquants = ids - produits.keys()
    if manquants:
        raise HTTPException(status_code=404, detail=f"Produit(s) introuvable(s) : {', '.join(manquants)}")
    return produits


@router.get("/commandes-clients", response_model=list[CommandeClient])
def list_commandes_clients(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[CommandeClientDB]:
    query = apply_boutique_filter(db.query(CommandeClientDB), CommandeClientDB.boutique_id, current_user, boutique_id)
    return query.all()


@router.get("/commandes-clients/{commande_id}", response_model=CommandeClientDetail)
def get_commande_client(
    commande_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CommandeClientDetail:
    c = db.get(CommandeClientDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    assert_boutique_access(current_user, c.boutique_id)
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
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CommandeClientDetail:
    require_permission(db, current_user, COMMANDE_CLIENT)
    assert_boutique_access(current_user, payload.boutique_id)
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

    # Réserve le stock dès la prise de commande (quantité disponible inchangée, réservée augmentée) —
    # tant qu'elle n'est pas annulée ou livrée. cf. CDC 3.4/6.3 : "quantité réservée (commandes en cours)".
    if c.statut not in (StatutCommandeClient.annulee, StatutCommandeClient.livree):
        for a in payload.articles:
            stock = db.get(StockBoutiqueDB, (payload.boutique_id, a.produit_id))
            if stock:
                stock.quantite_reservee += a.quantite

    db.commit()

    notifier_client(
        db, c.client_nom,
        f"Bonjour {c.client_nom}, votre commande #{c.id} chez {nom_boutique(db, c.boutique_id)} a bien été reçue "
        f"({montant:,.0f} GNF). Nous vous tiendrons informé de son statut. — KFSTORE".replace(",", " "),
    )

    return get_commande_client(c.id, db, current_user)


@router.put("/commandes-clients/{commande_id}", response_model=CommandeClientDetail)
def update_commande_client(
    commande_id: str,
    payload: CommandeClientUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CommandeClientDetail:
    c = db.get(CommandeClientDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    require_permission(db, current_user, COMMANDE_CLIENT)
    assert_boutique_access(current_user, c.boutique_id)

    ancien_statut = c.statut
    etait_reservee = ancien_statut not in (StatutCommandeClient.annulee, StatutCommandeClient.livree)

    data = payload.model_dump(exclude_unset=True)
    articles = data.pop("articles", None)
    for field, value in data.items():
        setattr(c, field, value)

    if articles is not None:
        if c.statut != StatutCommandeClient.en_attente:
            raise HTTPException(status_code=400, detail="Seule une commande en attente peut être modifiée")
        if not articles:
            raise HTTPException(status_code=400, detail="La commande doit contenir au moins un article")
        produits = _produits_by_id(db, {a["produit_id"] for a in articles})

        # Libère la réservation liée aux anciennes lignes avant de les remplacer.
        if etait_reservee:
            for l in c.lignes:
                stock = db.get(StockBoutiqueDB, (c.boutique_id, l.produit_id))
                if stock:
                    stock.quantite_reservee = max(0, stock.quantite_reservee - l.quantite)

        for l in list(c.lignes):
            db.delete(l)
        db.flush()
        montant = 0.0
        for a in articles:
            prix = a["prix_unitaire"] if a.get("prix_unitaire") is not None else produits[a["produit_id"]].prix
            montant += a["quantite"] * prix
            db.add(LigneCommandeClientDB(id=str(uuid.uuid4())[:8], commande_id=c.id, produit_id=a["produit_id"], quantite=a["quantite"], prix_unitaire=prix))
        c.montant = montant

        # Ré-applique la réservation avec les nouvelles quantités (la commande reste en_attente ici).
        for a in articles:
            stock = db.get(StockBoutiqueDB, (c.boutique_id, a["produit_id"]))
            if stock:
                stock.quantite_reservee += a["quantite"]

        paiement = db.query(PaiementClientDB).filter(PaiementClientDB.reference == f"#{c.id}").first()
        if paiement:
            paiement.montant = montant
            paiement.client_nom = c.client_nom

    # Livraison : la marchandise quitte réellement le stock — motif obligatoire (cf. CDC 3.4).
    if c.statut == StatutCommandeClient.livree and ancien_statut != StatutCommandeClient.livree:
        now = datetime.now(timezone.utc)
        for l in c.lignes:
            stock = db.get(StockBoutiqueDB, (c.boutique_id, l.produit_id))
            if stock:
                stock.quantite_disponible -= l.quantite
                if etait_reservee:
                    stock.quantite_reservee = max(0, stock.quantite_reservee - l.quantite)
                stock.derniere_mouvement = now
            db.add(MouvementStockDB(
                id=str(uuid.uuid4())[:8], horodatage=now, produit_id=l.produit_id, boutique_id=c.boutique_id,
                motif=MotifMouvementStock.commande_client,
                operateur=f"{current_user.prenom} {current_user.nom}", quantite=-l.quantite,
            ))
    # Annulation d'une commande encore en cours : libère la réservation, rien n'a physiquement bougé.
    elif c.statut == StatutCommandeClient.annulee and etait_reservee and ancien_statut != StatutCommandeClient.annulee:
        for l in c.lignes:
            stock = db.get(StockBoutiqueDB, (c.boutique_id, l.produit_id))
            if stock:
                stock.quantite_reservee = max(0, stock.quantite_reservee - l.quantite)

    db.commit()
    return get_commande_client(commande_id, db, current_user)


@router.get("/commandes-fournisseurs", response_model=list[LigneCommandeFournisseur])
def list_commandes_fournisseurs(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[CommandeFournisseurDB]:
    query = apply_boutique_filter(db.query(CommandeFournisseurDB), CommandeFournisseurDB.boutique_id, current_user, boutique_id)
    return query.all()


@router.get("/commandes-fournisseurs/{commande_id}", response_model=CommandeFournisseurDetail)
def get_commande_fournisseur(
    commande_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CommandeFournisseurDetail:
    c = db.get(CommandeFournisseurDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    assert_boutique_access(current_user, c.boutique_id)
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
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CommandeFournisseurDetail:
    require_permission(db, current_user, COMMANDE_FOURNISSEUR_CREATION)
    assert_boutique_access(current_user, payload.boutique_id)
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
    return get_commande_fournisseur(c.id, db, current_user)


@router.put("/commandes-fournisseurs/{commande_id}", response_model=CommandeFournisseurDetail)
def update_commande_fournisseur(
    commande_id: str,
    payload: CommandeFournisseurUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CommandeFournisseurDetail:
    c = db.get(CommandeFournisseurDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    require_permission(db, current_user, COMMANDE_FOURNISSEUR_CREATION)
    assert_boutique_access(current_user, c.boutique_id)

    data = payload.model_dump(exclude_unset=True)
    articles = data.pop("articles", None)
    for field, value in data.items():
        setattr(c, field, value)

    if articles is not None:
        if c.statut != StatutCommandeFournisseur.brouillon:
            raise HTTPException(status_code=400, detail="Seule une commande en brouillon peut être modifiée")
        if not articles:
            raise HTTPException(status_code=400, detail="La commande doit contenir au moins un article")
        produits = _produits_by_id(db, {a["produit_id"] for a in articles})
        for l in list(c.lignes):
            db.delete(l)
        db.flush()
        montant = 0.0
        for a in articles:
            prix = a["prix_unitaire"] if a.get("prix_unitaire") is not None else produits[a["produit_id"]].prix
            montant += a["quantite"] * prix
            db.add(LigneCommandeFournisseurDB(id=str(uuid.uuid4())[:8], commande_id=c.id, produit_id=a["produit_id"], quantite=a["quantite"], prix_unitaire=prix, quantite_recue=0))
        c.montant = montant

    db.commit()
    return get_commande_fournisseur(commande_id, db, current_user)


@router.post("/commandes-fournisseurs/{commande_id}/reception", response_model=CommandeFournisseurDetail)
def receptionner_commande_fournisseur(
    commande_id: str,
    payload: ReceptionCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CommandeFournisseurDetail:
    c = db.get(CommandeFournisseurDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    require_permission(db, current_user, COMMANDE_FOURNISSEUR_RECEPTION)
    assert_boutique_access(current_user, c.boutique_id)
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

    complet = all(l.quantite_recue >= l.quantite for l in c.lignes)
    if complet:
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

    etat = "réceptionnée intégralement" if complet else "réceptionnée partiellement"
    notifier_gerants_boutique(
        db, c.boutique_id,
        f"Commande fournisseur #{c.id} {etat} pour {nom_boutique(db, c.boutique_id)}. — KFSTORE",
    )

    return get_commande_fournisseur(commande_id, db, current_user)


@router.put("/commandes-fournisseurs/{commande_id}/reception", response_model=CommandeFournisseurDetail)
def corriger_reception_commande_fournisseur(
    commande_id: str,
    payload: CorrectionReceptionCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CommandeFournisseurDetail:
    c = db.get(CommandeFournisseurDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    require_permission(db, current_user, COMMANDE_FOURNISSEUR_RECEPTION)
    assert_boutique_access(current_user, c.boutique_id)
    if not payload.lignes:
        raise HTTPException(status_code=400, detail="Aucune ligne à corriger")

    lignes_by_produit = {l.produit_id: l for l in c.lignes}
    for r in payload.lignes:
        ligne = lignes_by_produit.get(r.produit_id)
        if not ligne:
            raise HTTPException(status_code=400, detail=f"Produit {r.produit_id} absent de la commande")
        if r.quantite_recue < 0 or r.quantite_recue > ligne.quantite:
            raise HTTPException(status_code=400, detail=f"La quantité corrigée pour {r.produit_id} doit être comprise entre 0 et {ligne.quantite}")

    now = datetime.now(timezone.utc)
    etait_receptionnee = c.statut == StatutCommandeFournisseur.receptionnee
    for r in payload.lignes:
        ligne = lignes_by_produit[r.produit_id]
        delta = r.quantite_recue - ligne.quantite_recue
        if delta == 0:
            continue
        ligne.quantite_recue = r.quantite_recue

        stock = db.get(StockBoutiqueDB, (c.boutique_id, r.produit_id))
        if stock:
            stock.quantite_disponible = max(stock.quantite_disponible + delta, 0)
            stock.derniere_mouvement = now
        elif delta > 0:
            db.add(StockBoutiqueDB(
                boutique_id=c.boutique_id, produit_id=r.produit_id,
                quantite_disponible=max(delta, 0), quantite_reservee=0, seuil_alerte=0, derniere_mouvement=now,
            ))
        db.add(MouvementStockDB(
            id=str(uuid.uuid4())[:8], horodatage=now, produit_id=r.produit_id, boutique_id=c.boutique_id,
            motif=MotifMouvementStock.correction_inventaire, operateur=payload.operateur, quantite=delta,
        ))

    if all(l.quantite_recue >= l.quantite for l in c.lignes):
        c.statut = StatutCommandeFournisseur.receptionnee
        c.date_reception = c.date_reception or date.today()
        if not etait_receptionnee:
            fournisseur = db.get(FournisseurDB, c.fournisseur_id)
            db.add(PaiementFournisseurDB(
                id=str(uuid.uuid4())[:8], fournisseur_nom=fournisseur.nom if fournisseur else c.fournisseur_id,
                reference=f"#{c.id}", boutique_id=c.boutique_id, mode_paiement=ModePaiement.virement,
                date=date.today(), montant=c.montant, statut=StatutPaiement.en_attente,
            ))
    else:
        c.statut = StatutCommandeFournisseur.receptionnee_partielle if any(l.quantite_recue > 0 for l in c.lignes) else StatutCommandeFournisseur.validee
        c.date_reception = None
        if etait_receptionnee:
            paiement = db.query(PaiementFournisseurDB).filter(
                PaiementFournisseurDB.reference == f"#{c.id}", PaiementFournisseurDB.statut == StatutPaiement.en_attente,
            ).first()
            if paiement:
                db.delete(paiement)

    db.commit()
    return get_commande_fournisseur(commande_id, db, current_user)
