import uuid
from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import apply_boutique_filter, assert_boutique_access, require_permission
from app.core.database import get_db
from app.core.module_actions import DETTE_CREATION, DETTE_REMBOURSEMENT
from app.core.security import get_current_user
from app.db_models.models import (
    CaisseDB,
    ClientDB,
    DemandeCreditDB,
    DetteDB,
    FournisseurDB,
    MouvementCaisseDB,
    PaiementClientDB,
    PaiementFournisseurDB,
    RemboursementDB,
    UtilisateurDB,
)
from app.models.schemas import DemandeCredit, Remboursement, StatutCaisse, StatutDemandeCredit, StatutDette, StatutPaiement, TiersType, TypeMouvementCaisse
from app.models.write_schemas import DetteCreate, RemboursementCreate
from app.services.audit import log_audit
from app.services.sms import get_sms_provider

router = APIRouter(prefix="/api/v1/dettes", tags=["dettes"])


class LigneDette(BaseModel):
    id: str
    tiers_nom: str
    client_id: str | None = None
    boutique_id: str
    montant_initial: float
    solde_restant: float
    echeance: str
    statut: str


def _to_ligne(d: DetteDB) -> LigneDette:
    return LigneDette(
        id=d.id,
        tiers_nom=d.tiers_nom,
        client_id=d.client_id,
        boutique_id=d.boutique_id,
        montant_initial=d.montant_initial,
        solde_restant=d.solde_restant,
        echeance=d.echeance.isoformat(),
        statut=d.statut,
    )


@router.get("", response_model=list[LigneDette])
def list_dettes(
    tiers_type: TiersType | None = None,
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[LigneDette]:
    query = apply_boutique_filter(db.query(DetteDB), DetteDB.boutique_id, current_user, boutique_id)
    if tiers_type:
        query = query.filter(DetteDB.tiers_type == tiers_type)
    return [_to_ligne(d) for d in query.all()]


@router.post("", response_model=LigneDette, status_code=201)
def create_dette(
    payload: DetteCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LigneDette:
    require_permission(db, current_user, DETTE_CREATION)
    assert_boutique_access(current_user, payload.boutique_id)
    auteur = f"{current_user.prenom} {current_user.nom}"
    d = DetteDB(
        id=str(uuid.uuid4())[:8],
        tiers_type=payload.tiers_type,
        tiers_nom=payload.tiers_nom,
        client_id=payload.client_id,
        boutique_id=payload.boutique_id,
        montant_initial=payload.montant_initial,
        solde_restant=payload.montant_initial,
        echeance=payload.echeance,
        statut=StatutDette.en_cours,
        created_by=auteur,
        updated_by=auteur,
    )
    db.add(d)
    db.commit()
    return _to_ligne(d)


@router.get("/remboursements", response_model=list[Remboursement])
def list_remboursements(
    dette_id: str | None = None,
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[RemboursementDB]:
    query = apply_boutique_filter(
        db.query(RemboursementDB).join(DetteDB, RemboursementDB.dette_id == DetteDB.id),
        DetteDB.boutique_id, current_user, boutique_id,
    )
    if dette_id:
        query = query.filter(RemboursementDB.dette_id == dette_id)
    return query.all()


@router.post("/{dette_id}/remboursements", response_model=LigneDette, status_code=201)
def encaisser_remboursement(
    dette_id: str,
    payload: RemboursementCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LigneDette:
    d = db.get(DetteDB, dette_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dette introuvable")
    require_permission(db, current_user, DETTE_REMBOURSEMENT)
    assert_boutique_access(current_user, d.boutique_id)
    if payload.montant > d.solde_restant:
        raise HTTPException(status_code=400, detail="Le montant dépasse le solde restant")

    caisse = db.get(CaisseDB, payload.caisse_id)
    if not caisse:
        raise HTTPException(status_code=404, detail="Caisse introuvable")
    if caisse.boutique_id != d.boutique_id:
        raise HTTPException(status_code=400, detail="Cette caisse n'appartient pas à la boutique de la dette")
    if caisse.statut != StatutCaisse.ouverte:
        raise HTTPException(status_code=400, detail="La caisse doit être ouverte pour enregistrer un encaissement")

    auteur = f"{current_user.prenom} {current_user.nom}"
    r = RemboursementDB(
        id=str(uuid.uuid4())[:8],
        dette_id=dette_id,
        caisse_id=payload.caisse_id,
        montant=payload.montant,
        mode_paiement=payload.mode_paiement,
        date=date.today(),
        operateur=payload.operateur,
        created_by=auteur,
        updated_by=auteur,
    )
    db.add(r)

    d.solde_restant -= payload.montant
    d.statut = StatutDette.soldee if d.solde_restant <= 0 else StatutDette.en_cours
    d.updated_by = auteur

    # Une créance client encaissée fait rentrer de l'argent en caisse ; une dette fournisseur réglée en fait sortir.
    type_mouvement = TypeMouvementCaisse.encaissement if d.tiers_type == TiersType.client else TypeMouvementCaisse.decaissement
    signed_montant = payload.montant if type_mouvement == TypeMouvementCaisse.encaissement else -payload.montant
    db.add(MouvementCaisseDB(
        id=str(uuid.uuid4())[:8], horodatage=datetime.now(timezone.utc), boutique_id=caisse.boutique_id,
        caisse_id=caisse.id, caisse_libelle=caisse.libelle, type=type_mouvement,
        motif=f"Remboursement dette — {d.tiers_nom}", operateur=payload.operateur, montant=signed_montant,
        created_by=auteur, updated_by=auteur,
    ))
    caisse.solde_theorique += signed_montant
    caisse.updated_by = auteur

    if d.tiers_type == TiersType.client:
        db.add(PaiementClientDB(
            id=str(uuid.uuid4())[:8], client_nom=d.tiers_nom, reference="Dette — remboursement",
            boutique_id=d.boutique_id, mode_paiement=payload.mode_paiement, date=date.today(),
            montant=payload.montant, statut=StatutPaiement.encaisse,
            created_by=auteur, updated_by=auteur,
        ))
    else:
        db.add(PaiementFournisseurDB(
            id=str(uuid.uuid4())[:8], fournisseur_nom=d.tiers_nom, reference="Dette — remboursement",
            boutique_id=d.boutique_id, mode_paiement=payload.mode_paiement, date=date.today(),
            montant=payload.montant, statut=StatutPaiement.paye,
            created_by=auteur, updated_by=auteur,
        ))

    db.commit()
    return _to_ligne(d)


@router.post("/{dette_id}/rappel-sms", response_model=LigneDette)
def envoyer_rappel_sms(
    dette_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LigneDette:
    """Relance SMS à l'approche/dépassement de l'échéance (cf. CDC §6.4 :
    "relances automatiques (SMS/WhatsApp/notification)")."""
    d = db.get(DetteDB, dette_id)
    if not d:
        raise HTTPException(status_code=404, detail="Dette introuvable")
    require_permission(db, current_user, DETTE_CREATION)
    assert_boutique_access(current_user, d.boutique_id)

    if d.tiers_type == TiersType.client:
        tiers = db.query(ClientDB).filter(ClientDB.nom == d.tiers_nom).first()
    else:
        tiers = db.query(FournisseurDB).filter(FournisseurDB.nom == d.tiers_nom).first()
    if not tiers or not tiers.contact:
        raise HTTPException(status_code=404, detail="Aucun numéro de contact enregistré pour ce tiers")

    montant = f"{d.solde_restant:,.0f}".replace(",", " ")
    message = (
        f"KFSTORE — Rappel : solde restant dû de {montant} GNF, "
        f"échéance le {d.echeance.strftime('%d/%m/%Y')}. Merci de régulariser."
    )
    if not get_sms_provider().send(tiers.contact, message):
        raise HTTPException(status_code=502, detail="Échec de l'envoi du SMS")

    log_audit(db, f"Rappel SMS envoyé — {d.tiers_nom} ({montant} GNF)", f"{current_user.prenom} {current_user.nom}", d.boutique_id)
    db.commit()
    return _to_ligne(d)


@router.get("/demandes-credit", response_model=list[DemandeCredit])
def list_demandes_credit(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[DemandeCredit]:
    """Demandes de crédit initiées depuis l'appli mobile client, en attente de décision
    staff (CDC §3.1/§3.8) — jamais de dette créée sans cette validation."""
    query = apply_boutique_filter(db.query(DemandeCreditDB), DemandeCreditDB.boutique_id, current_user, boutique_id)
    demandes = sorted(query.all(), key=lambda d: d.date_creation, reverse=True)
    clients_by_id = {c.id: c for c in db.query(ClientDB).all()}
    return [
        DemandeCredit(
            id=d.id, client_id=d.client_id, client_nom=clients_by_id[d.client_id].nom if d.client_id in clients_by_id else "—",
            boutique_id=d.boutique_id, montant_souhaite=d.montant_souhaite, motif=d.motif,
            statut=d.statut, date_creation=d.date_creation,
        )
        for d in demandes
    ]


@router.post("/demandes-credit/{demande_id}/valider", response_model=DemandeCredit)
def valider_demande_credit(
    demande_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> DemandeCredit:
    d = db.get(DemandeCreditDB, demande_id)
    if not d:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    require_permission(db, current_user, DETTE_CREATION)
    assert_boutique_access(current_user, d.boutique_id)
    if d.statut != StatutDemandeCredit.en_attente:
        raise HTTPException(status_code=400, detail="Cette demande a déjà été traitée")

    client = db.get(ClientDB, d.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    auteur = f"{current_user.prenom} {current_user.nom}"

    dette = DetteDB(
        id=str(uuid.uuid4())[:8], tiers_type=TiersType.client, tiers_nom=client.nom, client_id=client.id,
        boutique_id=d.boutique_id, montant_initial=d.montant_souhaite, solde_restant=d.montant_souhaite,
        echeance=date.today() + timedelta(days=30), statut=StatutDette.en_cours,
        created_by=auteur, updated_by=auteur,
    )
    db.add(dette)
    d.statut = StatutDemandeCredit.validee
    d.updated_by = auteur
    log_audit(db, f"Demande de crédit validée — {client.nom} ({d.montant_souhaite:,.0f} GNF)".replace(",", " "), auteur, d.boutique_id)
    db.commit()
    db.refresh(d)
    return DemandeCredit(
        id=d.id, client_id=d.client_id, client_nom=client.nom, boutique_id=d.boutique_id,
        montant_souhaite=d.montant_souhaite, motif=d.motif, statut=d.statut, date_creation=d.date_creation,
    )


@router.post("/demandes-credit/{demande_id}/refuser", response_model=DemandeCredit)
def refuser_demande_credit(
    demande_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> DemandeCredit:
    d = db.get(DemandeCreditDB, demande_id)
    if not d:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    require_permission(db, current_user, DETTE_CREATION)
    assert_boutique_access(current_user, d.boutique_id)
    if d.statut != StatutDemandeCredit.en_attente:
        raise HTTPException(status_code=400, detail="Cette demande a déjà été traitée")

    d.statut = StatutDemandeCredit.refusee
    d.updated_by = f"{current_user.prenom} {current_user.nom}"
    log_audit(db, f"Demande de crédit refusée — #{d.id}", f"{current_user.prenom} {current_user.nom}", d.boutique_id)
    db.commit()
    db.refresh(d)
    client = db.get(ClientDB, d.client_id)
    return DemandeCredit(
        id=d.id, client_id=d.client_id, client_nom=client.nom if client else "—", boutique_id=d.boutique_id,
        montant_souhaite=d.montant_souhaite, motif=d.motif, statut=d.statut, date_creation=d.date_creation,
    )
