import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import apply_boutique_filter, assert_boutique_access, require_permission, require_separation_des_taches
from app.core.database import get_db
from app.core.module_actions import COMMANDE_CLIENT, COMMANDE_FOURNISSEUR_CREATION, COMMANDE_FOURNISSEUR_RECEPTION, REMISE_VALIDATION
from app.core.security import get_current_user
from app.db_models.models import (
    CommandeClientDB,
    CommandeFournisseurDB,
    DetteDB,
    BeneficiaireDB,
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
    PalierPrix,
    StatutCommandeClient,
    StatutCommandeFournisseur,
    StatutDette,
    StatutPaiement,
    StatutValidationRemise,
    TiersType,
)
from app.services.bareme_credit import plafond_disponible
from app.models.write_schemas import (
    CommandeClientCreate,
    CommandeClientUpdate,
    CommandeFournisseurCreate,
    CommandeFournisseurUpdate,
    CorrectionReceptionCreate,
    ReceptionCreate,
)
from app.services.audit import log_audit
from app.services.notifications import nom_boutique, notifier_client, notifier_gerants_boutique
from app.services.pricing import prix_achat_effectif_a_date, prix_effectif_a_date

router = APIRouter(prefix="/api/v1", tags=["commandes"])

# Au-delà de cette remise (part du prix catalogue non facturée), un motif devient obligatoire
# et la commande reste bloquée en attente de validation (gérant ou siège) avant de pouvoir être
# livrée — cf. décision produit du 2026-08-13, même logique anti-fraude que les dépenses
# (SEUIL_VALIDATION_SIEGE dans app/routers/depenses.py).
SEUIL_REMISE = 0.10


def _evaluer_remise(articles_prix: list[tuple[int, float, float]], motif: str | None) -> tuple[StatutValidationRemise, str | None]:
    """Calcule la remise appliquée (prix catalogue vs prix facturé) à partir d'une liste de
    (quantite, prix_catalogue, prix_facture) et retourne le statut de validation à appliquer.
    Lève une erreur si la remise dépasse le seuil sans motif — jamais confiance dans un calcul
    de remise fait côté client, on le refait ici à partir du prix catalogue en base."""
    total_catalogue = sum(qte * prix_catalogue for qte, prix_catalogue, _ in articles_prix)
    total_facture = sum(qte * prix_facture for qte, _, prix_facture in articles_prix)
    remise_pct = (total_catalogue - total_facture) / total_catalogue if total_catalogue > 0 else 0.0
    if remise_pct > SEUIL_REMISE:
        if not motif:
            raise HTTPException(
                status_code=400,
                detail=f"Motif obligatoire pour une remise supérieure à {int(SEUIL_REMISE * 100)} % du prix catalogue",
            )
        return StatutValidationRemise.en_attente, motif
    return StatutValidationRemise.aucune, motif


def appliquer_livraison_stock(
    db: Session, c: CommandeClientDB, ancien_statut: StatutCommandeClient, operateur: str
) -> None:
    """Sort réellement la marchandise du stock lors du passage d'une commande à 'livrée'
    (et libère la réservation si elle existait), avec mouvement de stock motivé — cf. CDC
    3.4. Le statut de la commande doit déjà avoir été mis à jour par l'appelant ; on lui
    passe le statut PRÉCÉDENT pour savoir si une réservation était active. Réutilisée par
    la mise à jour directe d'une commande et par l'affectation de statut d'une livraison."""
    etait_reservee = ancien_statut not in (StatutCommandeClient.annulee, StatutCommandeClient.livree)
    now = datetime.now(timezone.utc)
    for l in c.lignes:
        stock = db.get(StockBoutiqueDB, (c.boutique_id, l.produit_id))
        stock_avant = stock.quantite_disponible if stock else 0
        if stock:
            stock.quantite_disponible -= l.quantite
            if etait_reservee:
                stock.quantite_reservee = max(0, stock.quantite_reservee - l.quantite)
            stock.derniere_mouvement = now
            # Jamais bloquant (une vente déjà encaissée, notamment synchronisée depuis le mode
            # hors-ligne mobile, doit toujours s'appliquer — CDC §3.7/§8) : un stock qui passe
            # sous zéro est accepté puis simplement signalé au gérant pour régularisation.
            if stock.quantite_disponible < 0:
                produit = db.get(ProduitDB, l.produit_id)
                log_audit(
                    db, f"Stock négatif après vente — {produit.nom if produit else l.produit_id} "
                    f"({stock.quantite_disponible})", operateur, c.boutique_id,
                )
                notifier_gerants_boutique(
                    db, c.boutique_id,
                    f"Stock négatif détecté sur {produit.nom if produit else l.produit_id} après une vente "
                    f"({stock.quantite_disponible}) — à régulariser. — KFSTORE",
                    titre="Stock négatif",
                )
        db.add(MouvementStockDB(
            id=str(uuid.uuid4())[:8], horodatage=now, produit_id=l.produit_id, boutique_id=c.boutique_id,
            motif=MotifMouvementStock.commande_client,
            operateur=operateur, quantite=-l.quantite,
            stock_avant=stock_avant, stock_apres=stock.quantite_disponible if stock else stock_avant - l.quantite,
        ))


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
    return _serialiser_commande_client(db, c)


def _serialiser_commande_client(db: Session, c: CommandeClientDB) -> CommandeClientDetail:
    produits = _produits_by_id(db, {l.produit_id for l in c.lignes}) if c.lignes else {}
    return CommandeClientDetail(
        id=c.id, client_nom=c.client_nom, client_id=c.client_id, boutique_id=c.boutique_id, canal=c.canal,
        mode_paiement=c.mode_paiement, montant=c.montant, statut=c.statut, date_creation=c.date_creation,
        remise_statut=c.remise_statut, remise_motif=c.remise_motif,
        remise_validee_par=c.remise_validee_par, remise_validee_le=c.remise_validee_le,
        articles=[
            ArticleCommande(
                id=l.id, produit_id=l.produit_id, produit_nom=produits[l.produit_id].nom,
                quantite=l.quantite, palier=l.palier, prix_unitaire=l.prix_unitaire,
                prix_catalogue_a_la_vente=prix_effectif_a_date(db, l.produit_id, c.boutique_id, l.palier, c.date_creation.date()),
            )
            for l in c.lignes
        ],
    )


def creer_commande_client(db: Session, payload: CommandeClientCreate, auteur: str) -> CommandeClientDB:
    """Cœur de la création d'une commande client — partagé entre la route interne
    (personnel, /commandes-clients) et la route de l'appli mobile client (/mes-commandes,
    cf. app/routers/mes_commandes.py) pour ne jamais faire diverger la logique de prix, de
    remise, de réservation de stock et de notification entre les deux canaux."""
    if not payload.articles:
        raise HTTPException(status_code=400, detail="La commande doit contenir au moins un article")
    produits = _produits_by_id(db, {a.produit_id for a in payload.articles})
    aujourdhui = date.today()

    c = CommandeClientDB(
        id=str(uuid.uuid4())[:8], client_nom=payload.client_nom, client_id=payload.client_id, boutique_id=payload.boutique_id,
        canal=payload.canal, mode_paiement=payload.mode_paiement, statut=payload.statut, montant=0.0,
        created_by=auteur, updated_by=auteur,
    )
    db.add(c)
    montant = 0.0
    articles_prix: list[tuple[int, float, float]] = []
    for a in payload.articles:
        prix_catalogue = prix_effectif_a_date(db, a.produit_id, payload.boutique_id, a.palier, aujourdhui) or 0.0
        prix = a.prix_unitaire if a.prix_unitaire is not None else prix_catalogue
        montant += a.quantite * prix
        articles_prix.append((a.quantite, prix_catalogue, prix))
        db.add(LigneCommandeClientDB(id=str(uuid.uuid4())[:8], commande_id=c.id, produit_id=a.produit_id, quantite=a.quantite, palier=a.palier, prix_unitaire=prix))
    c.montant = montant

    c.remise_statut, c.remise_motif = _evaluer_remise(articles_prix, payload.remise_motif)
    if c.remise_statut == StatutValidationRemise.en_attente:
        log_audit(
            db, f"Remise en attente de validation sur commande #{c.id} — motif : {c.remise_motif}",
            auteur, c.boutique_id,
        )
        notifier_gerants_boutique(
            db, c.boutique_id, f"Remise en attente de validation — commande #{c.id} ({c.client_nom}) — motif : {c.remise_motif}",
            titre="Remise à valider",
        )

    if payload.mode_paiement != ModePaiement.credit_client:
        statut_paiement = StatutPaiement.en_attente if payload.mode_paiement == ModePaiement.a_la_livraison else StatutPaiement.encaisse
        db.add(PaiementClientDB(
            id=str(uuid.uuid4())[:8], client_nom=c.client_nom, reference=f"#{c.id}", boutique_id=c.boutique_id,
            mode_paiement=payload.mode_paiement, date=date.today(), montant=montant, statut=statut_paiement,
        ))
    else:
        # Aide Humanitaire : le crédit générique (credit_autorise) n'a aujourd'hui aucun plafond
        # réellement appliqué — pour un bénéficiaire spécifiquement, la vente à crédit doit rester
        # dans le plafond disponible et crée automatiquement la dette correspondante (échéance 30
        # jours). Le crédit client générique hors bénéficiaire garde son comportement actuel
        # (réconciliation manuelle par le staff).
        beneficiaire = db.query(BeneficiaireDB).filter(BeneficiaireDB.client_id == payload.client_id).first() if payload.client_id else None
        if beneficiaire:
            if montant > plafond_disponible(db, beneficiaire):
                raise HTTPException(status_code=400, detail="Montant supérieur au plafond de crédit disponible pour ce bénéficiaire")
            db.add(DetteDB(
                id=str(uuid.uuid4())[:8], tiers_type=TiersType.client, tiers_nom=c.client_nom, client_id=payload.client_id,
                boutique_id=c.boutique_id, montant_initial=montant, solde_restant=montant,
                echeance=date.today() + timedelta(days=30), statut=StatutDette.en_cours,
                created_by=auteur, updated_by=auteur,
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

    db.refresh(c)
    return c


@router.post("/commandes-clients", response_model=CommandeClientDetail, status_code=201)
def create_commande_client(
    payload: CommandeClientCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CommandeClientDetail:
    require_permission(db, current_user, COMMANDE_CLIENT)
    assert_boutique_access(current_user, payload.boutique_id)
    auteur = f"{current_user.prenom} {current_user.nom}"
    c = creer_commande_client(db, payload, auteur)
    return _serialiser_commande_client(db, c)


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
    c.updated_by = f"{current_user.prenom} {current_user.nom}"

    if articles is not None:
        if c.statut != StatutCommandeClient.en_attente:
            raise HTTPException(status_code=400, detail="Seule une commande en attente peut être modifiée")
        if not articles:
            raise HTTPException(status_code=400, detail="La commande doit contenir au moins un article")
        produits = _produits_by_id(db, {a["produit_id"] for a in articles})
        aujourdhui = date.today()

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
        articles_prix: list[tuple[int, float, float]] = []
        for a in articles:
            palier = PalierPrix(a.get("palier", PalierPrix.detail.value))
            prix_catalogue = prix_effectif_a_date(db, a["produit_id"], c.boutique_id, palier, aujourdhui) or 0.0
            prix = a["prix_unitaire"] if a.get("prix_unitaire") is not None else prix_catalogue
            montant += a["quantite"] * prix
            articles_prix.append((a["quantite"], prix_catalogue, prix))
            db.add(LigneCommandeClientDB(id=str(uuid.uuid4())[:8], commande_id=c.id, produit_id=a["produit_id"], quantite=a["quantite"], palier=palier, prix_unitaire=prix))
        c.montant = montant
        c.remise_statut, c.remise_motif = _evaluer_remise(articles_prix, c.remise_motif)
        if c.remise_statut == StatutValidationRemise.en_attente:
            log_audit(
                db, f"Remise en attente de validation sur commande #{c.id} — motif : {c.remise_motif}",
                f"{current_user.prenom} {current_user.nom}", c.boutique_id,
            )
            notifier_gerants_boutique(
                db, c.boutique_id, f"Remise en attente de validation — commande #{c.id} ({c.client_nom}) — motif : {c.remise_motif}",
                titre="Remise à valider",
            )

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
        if c.remise_statut == StatutValidationRemise.en_attente:
            raise HTTPException(
                status_code=400,
                detail="Remise en attente de validation : impossible de livrer cette commande avant validation par un gérant ou le siège.",
            )
        appliquer_livraison_stock(db, c, ancien_statut, f"{current_user.prenom} {current_user.nom}")
    # Annulation d'une commande encore en cours : libère la réservation, rien n'a physiquement bougé.
    elif c.statut == StatutCommandeClient.annulee and etait_reservee and ancien_statut != StatutCommandeClient.annulee:
        for l in c.lignes:
            stock = db.get(StockBoutiqueDB, (c.boutique_id, l.produit_id))
            if stock:
                stock.quantite_reservee = max(0, stock.quantite_reservee - l.quantite)

    db.commit()
    return get_commande_client(commande_id, db, current_user)


@router.put("/commandes-clients/{commande_id}/valider-remise", response_model=CommandeClientDetail)
def valider_remise_commande_client(
    commande_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CommandeClientDetail:
    c = db.get(CommandeClientDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    require_permission(db, current_user, REMISE_VALIDATION)
    assert_boutique_access(current_user, c.boutique_id)
    if c.remise_statut != StatutValidationRemise.en_attente:
        raise HTTPException(status_code=400, detail="Cette commande n'a pas de remise en attente de validation")
    require_separation_des_taches(db, current_user, c.created_by)

    c.remise_statut = StatutValidationRemise.validee
    c.remise_validee_par = f"{current_user.prenom} {current_user.nom}"
    c.remise_validee_le = datetime.now(timezone.utc)
    log_audit(
        db, f"Remise validée sur commande #{c.id}", c.remise_validee_par, c.boutique_id,
        valeur_avant={"remise_statut": "en_attente"}, valeur_apres={"remise_statut": "validee"},
    )
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

    auteur = f"{current_user.prenom} {current_user.nom}"
    c = CommandeFournisseurDB(
        id=str(uuid.uuid4())[:8], fournisseur_id=payload.fournisseur_id, boutique_id=payload.boutique_id,
        date_attendue=payload.date_attendue, statut=payload.statut, montant=0.0,
        created_by=auteur, updated_by=auteur,
    )
    db.add(c)
    montant = 0.0
    for a in payload.articles:
        # Le palier sert ici de palier de volume négocié avec CE fournisseur (cf. prix_achats) —
        # à ne pas confondre avec les paliers détail/semi-gros/gros de vente client.
        prix = a.prix_unitaire if a.prix_unitaire is not None else (prix_achat_effectif_a_date(db, a.produit_id, payload.fournisseur_id, a.palier, date.today()) or 0.0)
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
            palier = PalierPrix(a.get("palier", PalierPrix.detail.value))
            prix = a.get("prix_unitaire") if a.get("prix_unitaire") is not None else (prix_achat_effectif_a_date(db, a["produit_id"], c.fournisseur_id, palier, date.today()) or 0.0)
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
        stock_avant = stock.quantite_disponible if stock else 0
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
            stock_avant=stock_avant, stock_apres=stock_avant + r.quantite,
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
        stock_avant = stock.quantite_disponible if stock else 0
        stock_apres = max(stock_avant + delta, 0)
        if stock:
            stock.quantite_disponible = stock_apres
            stock.derniere_mouvement = now
        elif delta > 0:
            db.add(StockBoutiqueDB(
                boutique_id=c.boutique_id, produit_id=r.produit_id,
                quantite_disponible=stock_apres, quantite_reservee=0, seuil_alerte=0, derniere_mouvement=now,
            ))
        db.add(MouvementStockDB(
            id=str(uuid.uuid4())[:8], horodatage=now, produit_id=r.produit_id, boutique_id=c.boutique_id,
            motif=MotifMouvementStock.correction_inventaire, operateur=payload.operateur, quantite=delta,
            stock_avant=stock_avant, stock_apres=stock_apres,
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
