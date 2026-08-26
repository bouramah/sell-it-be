import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.core.authorization import a_portee_reseau, apply_boutique_filter, assert_boutique_access, boutiques_autorisees, require_permission
from app.core.database import get_db
from app.core.module_actions import CLIENT_GESTION, ENCAISSEMENT
from app.core.security import get_current_user
from app.db_models.models import (
    BoutiqueDB,
    CaisseDB,
    ClientDB,
    CommandeClientDB,
    CommandeFournisseurDB,
    DetteDB,
    MouvementCaisseDB,
    PaiementClientDB,
    PaiementFournisseurDB,
    UtilisateurDB,
)
from app.models.schemas import (
    Client,
    PaiementClient,
    PaiementFournisseur,
    StatutCaisse,
    StatutCommandeClient,
    StatutPaiement,
    TiersType,
    TopClient,
    TypeMouvementCaisse,
)
from app.models.write_schemas import ClientCreate, ClientUpdate, PaiementCaisseInput, PaiementClientCreate, PaiementFournisseurCreate

router = APIRouter(prefix="/api/v1", tags=["clients"])

UPLOADS_DIR = Path(__file__).resolve().parents[2] / "uploads" / "paiements"
ALLOWED_DOCUMENT_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}


def _delete_document_file(document_url: str) -> None:
    filename = document_url.rsplit("/", 1)[-1]
    path = UPLOADS_DIR / filename
    if path.exists():
        path.unlink()


def _solde_dette(db: Session, client_nom: str) -> float:
    total = (
        db.query(func.coalesce(func.sum(DetteDB.solde_restant), 0.0))
        .filter(DetteDB.tiers_type == TiersType.client, DetteDB.tiers_nom == client_nom)
        .scalar()
    )
    return float(total or 0.0)


def _to_schema(c: ClientDB, db: Session) -> Client:
    return Client(
        id=c.id,
        nom=c.nom,
        contact=c.contact,
        boutique_ids=[b.id for b in c.boutiques],
        segment=c.segment,
        credit_autorise=c.credit_autorise,
        solde_dette=_solde_dette(db, c.nom),
        quartier=c.quartier,
        commune=c.commune,
        ville=c.ville,
        secteur_geo_id=c.secteur_geo_id,
    )


def _assert_client_boutiques_access(current_user: UtilisateurDB, boutique_ids: list[str]) -> None:
    if a_portee_reseau(current_user):
        return
    autorisees = boutiques_autorisees(current_user)
    if not all(bid in autorisees for bid in boutique_ids):
        raise HTTPException(status_code=403, detail="Vous n'avez pas accès à une des boutiques indiquées")


@router.get("/clients", response_model=list[Client])
def list_clients(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[Client]:
    query = db.query(ClientDB)
    if boutique_id:
        assert_boutique_access(current_user, boutique_id)
        query = query.filter(ClientDB.boutiques.any(BoutiqueDB.id == boutique_id))
    elif not a_portee_reseau(current_user):
        query = query.filter(ClientDB.boutiques.any(BoutiqueDB.id.in_(boutiques_autorisees(current_user))))
    return [_to_schema(c, db) for c in query.all()]


@router.get("/clients/top", response_model=list[TopClient])
def top_clients(
    boutique_id: str | None = None,
    limite: int = 10,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[TopClient]:
    """Classement des clients par chiffre d'affaires — pour le tableau de bord comparatif
    clients (CDC demande client). Ne compte que les clients enregistrés (client_id renseigné) ;
    les ventes à un client de passage sans fiche ne sont pas attribuables à un client précis."""
    query = db.query(CommandeClientDB).filter(
        CommandeClientDB.statut != StatutCommandeClient.annulee,
        CommandeClientDB.client_id.isnot(None),
    )
    if boutique_id:
        assert_boutique_access(current_user, boutique_id)
        query = query.filter(CommandeClientDB.boutique_id == boutique_id)
    elif not a_portee_reseau(current_user):
        query = query.filter(CommandeClientDB.boutique_id.in_(boutiques_autorisees(current_user)))
    commandes = query.all()

    agrege: dict[str, dict] = {}
    for c in commandes:
        entry = agrege.setdefault(c.client_id, {"nom": c.client_nom, "ca": 0.0, "nb": 0})
        entry["ca"] += c.montant
        entry["nb"] += 1

    classement = sorted(agrege.items(), key=lambda kv: kv[1]["ca"], reverse=True)[:limite]
    return [
        TopClient(client_id=cid, client_nom=entry["nom"], chiffre_affaires=entry["ca"], nombre_commandes=entry["nb"])
        for cid, entry in classement
    ]


@router.post("/clients", response_model=Client, status_code=201)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Client:
    require_permission(db, current_user, CLIENT_GESTION)
    _assert_client_boutiques_access(current_user, payload.boutique_ids)
    data = payload.model_dump(exclude={"boutique_ids"})
    boutiques = db.query(BoutiqueDB).filter(BoutiqueDB.id.in_(payload.boutique_ids)).all()
    auteur = f"{current_user.prenom} {current_user.nom}"
    c = ClientDB(id=str(uuid.uuid4())[:8], boutiques=boutiques, created_by=auteur, updated_by=auteur, **data)
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_schema(c, db)


@router.put("/clients/{client_id}", response_model=Client)
def update_client(
    client_id: str,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Client:
    c = db.get(ClientDB, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client introuvable")
    require_permission(db, current_user, CLIENT_GESTION)
    _assert_client_boutiques_access(current_user, [b.id for b in c.boutiques])
    if payload.boutique_ids is not None:
        _assert_client_boutiques_access(current_user, payload.boutique_ids)
    data = payload.model_dump(exclude_unset=True, exclude={"boutique_ids"})
    for field, value in data.items():
        setattr(c, field, value)
    if payload.boutique_ids is not None:
        c.boutiques = db.query(BoutiqueDB).filter(BoutiqueDB.id.in_(payload.boutique_ids)).all()
    c.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(c)
    return _to_schema(c, db)


@router.delete("/clients/{client_id}", status_code=204)
def delete_client(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    c = db.get(ClientDB, client_id)
    if not c:
        raise HTTPException(status_code=404, detail="Client introuvable")
    require_permission(db, current_user, CLIENT_GESTION)
    _assert_client_boutiques_access(current_user, [b.id for b in c.boutiques])
    db.delete(c)
    db.commit()


@router.get("/paiements-clients", response_model=list[PaiementClient])
def list_paiements_clients(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[PaiementClientDB]:
    query = apply_boutique_filter(db.query(PaiementClientDB), PaiementClientDB.boutique_id, current_user, boutique_id)
    return sorted(query.all(), key=lambda p: p.date, reverse=True)


@router.get("/paiements-fournisseurs", response_model=list[PaiementFournisseur])
def list_paiements_fournisseurs(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[PaiementFournisseurDB]:
    query = apply_boutique_filter(db.query(PaiementFournisseurDB), PaiementFournisseurDB.boutique_id, current_user, boutique_id)
    return sorted(query.all(), key=lambda p: p.date, reverse=True)


def _deja_paye(db: Session, model, reference: str) -> float:
    total = db.query(func.coalesce(func.sum(model.montant), 0.0)).filter(model.reference == reference).scalar()
    return float(total or 0.0)


def _caisse_pour_mouvement(db: Session, caisse_id: str, boutique_id: str) -> CaisseDB:
    caisse = db.get(CaisseDB, caisse_id)
    if not caisse:
        raise HTTPException(status_code=404, detail="Caisse introuvable")
    if caisse.boutique_id != boutique_id:
        raise HTTPException(status_code=400, detail="Cette caisse n'appartient pas à la boutique sélectionnée")
    if caisse.statut != StatutCaisse.ouverte:
        raise HTTPException(status_code=400, detail="La caisse doit être ouverte pour enregistrer un paiement")
    return caisse


def _mouvement_caisse(db: Session, caisse: CaisseDB, type_mouvement: TypeMouvementCaisse, motif: str, operateur: str, montant: float) -> None:
    signed_montant = montant if type_mouvement == TypeMouvementCaisse.encaissement else -montant
    db.add(MouvementCaisseDB(
        id=str(uuid.uuid4())[:8], horodatage=datetime.now(timezone.utc), boutique_id=caisse.boutique_id,
        caisse_id=caisse.id, caisse_libelle=caisse.libelle, type=type_mouvement,
        motif=motif, operateur=operateur, montant=signed_montant,
    ))
    caisse.solde_theorique += signed_montant


@router.post("/paiements-clients", response_model=PaiementClient, status_code=201)
def create_paiement_client(
    payload: PaiementClientCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PaiementClientDB:
    require_permission(db, current_user, ENCAISSEMENT)
    assert_boutique_access(current_user, payload.boutique_id)
    statut = StatutPaiement.encaisse
    reference = "Paiement direct"
    if payload.commande_id:
        commande = db.get(CommandeClientDB, payload.commande_id)
        if not commande:
            raise HTTPException(status_code=404, detail="Commande introuvable")
        reference = f"#{payload.commande_id}"
        restant = commande.montant - _deja_paye(db, PaiementClientDB, reference)
        if payload.montant <= 0:
            raise HTTPException(status_code=400, detail="Le montant doit être positif")
        if payload.montant > restant + 0.01:
            raise HTTPException(status_code=400, detail=f"Le montant dépasse le solde restant ({restant:.0f} GNF)")
        statut = StatutPaiement.encaisse if payload.montant >= restant - 0.01 else StatutPaiement.partiel

    caisse = _caisse_pour_mouvement(db, payload.caisse_id, payload.boutique_id)
    client_nom = payload.client_nom.strip() or "Client de passage"

    p = PaiementClientDB(
        id=str(uuid.uuid4())[:8], client_nom=client_nom, reference=reference, boutique_id=payload.boutique_id,
        caisse_id=payload.caisse_id, mode_paiement=payload.mode_paiement,
        date=payload.date_paiement or date.today(), montant=payload.montant, statut=statut,
    )
    db.add(p)

    _mouvement_caisse(
        db, caisse, TypeMouvementCaisse.encaissement,
        f"Paiement client — {client_nom}", f"{current_user.prenom} {current_user.nom}", payload.montant,
    )

    db.commit()
    db.refresh(p)
    return p


@router.post("/paiements-fournisseurs", response_model=PaiementFournisseur, status_code=201)
def create_paiement_fournisseur(
    payload: PaiementFournisseurCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PaiementFournisseurDB:
    require_permission(db, current_user, ENCAISSEMENT)
    assert_boutique_access(current_user, payload.boutique_id)
    statut = StatutPaiement.paye
    reference = "Paiement direct"
    if payload.commande_id:
        commande = db.get(CommandeFournisseurDB, payload.commande_id)
        if not commande:
            raise HTTPException(status_code=404, detail="Commande introuvable")
        reference = f"#{payload.commande_id}"
        restant = commande.montant - _deja_paye(db, PaiementFournisseurDB, reference)
        if payload.montant <= 0:
            raise HTTPException(status_code=400, detail="Le montant doit être positif")
        if payload.montant > restant + 0.01:
            raise HTTPException(status_code=400, detail=f"Le montant dépasse le solde restant ({restant:.0f} GNF)")
        statut = StatutPaiement.paye if payload.montant >= restant - 0.01 else StatutPaiement.partiel

    caisse = _caisse_pour_mouvement(db, payload.caisse_id, payload.boutique_id)

    p = PaiementFournisseurDB(
        id=str(uuid.uuid4())[:8], fournisseur_nom=payload.fournisseur_nom, reference=reference, boutique_id=payload.boutique_id,
        caisse_id=payload.caisse_id, mode_paiement=payload.mode_paiement,
        date=payload.date_paiement or date.today(), montant=payload.montant, statut=statut,
    )
    db.add(p)

    _mouvement_caisse(
        db, caisse, TypeMouvementCaisse.decaissement,
        f"Paiement fournisseur — {payload.fournisseur_nom}", f"{current_user.prenom} {current_user.nom}", payload.montant,
    )

    db.commit()
    db.refresh(p)
    return p


@router.post("/paiements-clients/{paiement_id}/encaisser", response_model=PaiementClient)
def encaisser_paiement_client(
    paiement_id: str,
    payload: PaiementCaisseInput,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PaiementClientDB:
    p = db.get(PaiementClientDB, paiement_id)
    if not p:
        raise HTTPException(status_code=404, detail="Paiement introuvable")
    require_permission(db, current_user, ENCAISSEMENT)
    assert_boutique_access(current_user, p.boutique_id)
    if p.statut in (StatutPaiement.encaisse, StatutPaiement.paye):
        raise HTTPException(status_code=400, detail="Ce paiement est déjà encaissé")

    caisse = _caisse_pour_mouvement(db, payload.caisse_id, p.boutique_id)

    _mouvement_caisse(
        db, caisse, TypeMouvementCaisse.encaissement,
        f"Paiement client — {p.client_nom}", f"{current_user.prenom} {current_user.nom}", p.montant,
    )
    p.statut = StatutPaiement.encaisse
    p.caisse_id = payload.caisse_id

    db.commit()
    db.refresh(p)
    return p


@router.post("/paiements-fournisseurs/{paiement_id}/payer", response_model=PaiementFournisseur)
def marquer_paiement_fournisseur_paye(
    paiement_id: str,
    payload: PaiementCaisseInput,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PaiementFournisseurDB:
    p = db.get(PaiementFournisseurDB, paiement_id)
    if not p:
        raise HTTPException(status_code=404, detail="Paiement introuvable")
    require_permission(db, current_user, ENCAISSEMENT)
    assert_boutique_access(current_user, p.boutique_id)
    if p.statut == StatutPaiement.paye:
        raise HTTPException(status_code=400, detail="Ce paiement est déjà réglé")

    caisse = _caisse_pour_mouvement(db, payload.caisse_id, p.boutique_id)

    _mouvement_caisse(
        db, caisse, TypeMouvementCaisse.decaissement,
        f"Paiement fournisseur — {p.fournisseur_nom}", f"{current_user.prenom} {current_user.nom}", p.montant,
    )
    p.statut = StatutPaiement.paye
    p.caisse_id = payload.caisse_id

    db.commit()
    db.refresh(p)
    return p


@router.post("/paiements-fournisseurs/{paiement_id}/document", response_model=PaiementFournisseur)
def uploader_document_paiement_fournisseur(
    paiement_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PaiementFournisseurDB:
    p = db.get(PaiementFournisseurDB, paiement_id)
    if not p:
        raise HTTPException(status_code=404, detail="Paiement introuvable")
    require_permission(db, current_user, ENCAISSEMENT)
    assert_boutique_access(current_user, p.boutique_id)

    ext = ALLOWED_DOCUMENT_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="Format non supporté (jpeg, png, webp, pdf uniquement)")

    if p.document_url:
        _delete_document_file(p.document_url)

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{paiement_id}-{uuid.uuid4().hex[:8]}{ext}"
    with open(UPLOADS_DIR / filename, "wb") as f:
        f.write(file.file.read())

    p.document_url = f"/uploads/paiements/{filename}"
    db.commit()
    db.refresh(p)
    return p


@router.delete("/paiements-fournisseurs/{paiement_id}/document", response_model=PaiementFournisseur)
def supprimer_document_paiement_fournisseur(
    paiement_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PaiementFournisseurDB:
    p = db.get(PaiementFournisseurDB, paiement_id)
    if not p:
        raise HTTPException(status_code=404, detail="Paiement introuvable")
    require_permission(db, current_user, ENCAISSEMENT)
    assert_boutique_access(current_user, p.boutique_id)
    if p.document_url:
        _delete_document_file(p.document_url)
        p.document_url = None
        db.commit()
        db.refresh(p)
    return p
