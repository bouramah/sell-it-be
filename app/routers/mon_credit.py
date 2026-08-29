"""Crédit client — CDC §3.1/§3.8 : consultation du solde/échéances/historique et initiation
d'une demande de crédit ou d'une notification de remboursement depuis l'appli mobile client —
"toute demande étant reçue et validée par la boutique concernée avant prise en compte
effective". Aucune écriture comptable n'est jamais créée directement depuis ce routeur : une
demande de crédit reste "en_attente" jusqu'à validation staff (cf. dettes.py), et une
notification de remboursement ne fait que prévenir la boutique — jamais d'encaissement
automatique (le staff enregistre le remboursement réel via /dettes/{id}/remboursements après
vérification physique des fonds reçus, même logique anti-fraude que le reste de la plateforme)."""
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import get_current_client
from app.db_models.models import BeneficiaireDB, BoutiqueDB, ClientDB, DemandeCreditDB, DetteDB, RemboursementDB
from app.models.schemas import DemandeCredit, Remboursement, StatutBoutique, StatutDemandeCredit, TiersType
from app.models.write_schemas import DemandeCreditCreate, NotifierRemboursementRequest
from app.services.audit import log_audit
from app.services.bareme_credit import plafond_disponible
from app.services.notifications import nom_boutique, notifier_gerants_boutique
from app.services.validation_garant import DemandeCreditBeneficiaireInput, creer_demande_credit_beneficiaire

router = APIRouter(prefix="/api/v1/mon-credit", tags=["mon-credit"])


class LigneDetteClient(BaseModel):
    id: str
    boutique_id: str
    montant_initial: float
    solde_restant: float
    echeance: str
    statut: str


class InfosBeneficiaire(BaseModel):
    etablissement_nom: str
    plafond_disponible: float
    plafond_suspendu: bool


class MonCredit(BaseModel):
    credit_autorise: bool
    solde_total: float
    dettes: list[LigneDetteClient]
    remboursements: list[Remboursement]
    beneficiaire: InfosBeneficiaire | None = None


class MessageResponse(BaseModel):
    message: str


def _mes_dettes(db: Session, client: ClientDB) -> list[DetteDB]:
    return db.query(DetteDB).filter(DetteDB.client_id == client.id, DetteDB.tiers_type == TiersType.client).all()


@router.get("", response_model=MonCredit)
def mon_credit(client: ClientDB = Depends(get_current_client), db: Session = Depends(get_db)) -> MonCredit:
    dettes = _mes_dettes(db, client)
    remboursements = (
        db.query(RemboursementDB).join(DetteDB).filter(DetteDB.client_id == client.id).order_by(RemboursementDB.date.desc()).all()
    )
    beneficiaire = db.query(BeneficiaireDB).filter(BeneficiaireDB.client_id == client.id).first()
    return MonCredit(
        credit_autorise=client.credit_autorise,
        solde_total=sum(d.solde_restant for d in dettes),
        beneficiaire=InfosBeneficiaire(
            etablissement_nom=beneficiaire.etablissement.nom, plafond_disponible=plafond_disponible(db, beneficiaire),
            plafond_suspendu=beneficiaire.plafond_suspendu,
        ) if beneficiaire else None,
        dettes=[
            LigneDetteClient(
                id=d.id, boutique_id=d.boutique_id, montant_initial=d.montant_initial,
                solde_restant=d.solde_restant, echeance=d.echeance.isoformat(), statut=d.statut,
            )
            for d in dettes
        ],
        remboursements=[
            Remboursement(
                id=r.id, dette_id=r.dette_id, caisse_id=r.caisse_id, montant=r.montant,
                mode_paiement=r.mode_paiement, date=r.date, operateur=r.operateur,
            )
            for r in remboursements
        ],
    )


@router.get("/demandes", response_model=list[DemandeCredit])
def mes_demandes_credit(client: ClientDB = Depends(get_current_client), db: Session = Depends(get_db)) -> list[DemandeCredit]:
    demandes = (
        db.query(DemandeCreditDB).filter(DemandeCreditDB.client_id == client.id).order_by(DemandeCreditDB.date_creation.desc()).all()
    )
    return [
        DemandeCredit(
            id=d.id, client_id=d.client_id, client_nom=client.nom, boutique_id=d.boutique_id,
            montant_souhaite=d.montant_souhaite, motif=d.motif, statut=d.statut, date_creation=d.date_creation,
        )
        for d in demandes
    ]


@router.post("/demandes", response_model=DemandeCredit, status_code=201)
def demander_credit(
    payload: DemandeCreditCreate, client: ClientDB = Depends(get_current_client), db: Session = Depends(get_db)
) -> DemandeCredit:
    if not client.credit_autorise:
        raise HTTPException(
            status_code=403,
            detail="Le crédit n'est pas encore activé sur votre compte. Rendez-vous en boutique pour l'activer.",
        )
    boutique = db.get(BoutiqueDB, payload.boutique_id)
    if not boutique or boutique.statut != StatutBoutique.active:
        raise HTTPException(status_code=404, detail="Boutique introuvable ou fermée")
    if payload.montant_souhaite <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")

    # Aide Humanitaire : circuit de validation par les garants (référent + comptabilité de
    # l'établissement), pas de validation staff — cf. app/services/validation_garant.py.
    beneficiaire = db.query(BeneficiaireDB).filter(BeneficiaireDB.client_id == client.id).first()
    if beneficiaire:
        try:
            d = creer_demande_credit_beneficiaire(
                db, beneficiaire,
                DemandeCreditBeneficiaireInput(boutique_id=payload.boutique_id, montant_souhaite=payload.montant_souhaite, motif=payload.motif),
                cree_par=f"{client.nom} (appli mobile client)",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        db.commit()
        db.refresh(d)
        return DemandeCredit(
            id=d.id, client_id=d.client_id, client_nom=client.nom, boutique_id=d.boutique_id,
            montant_souhaite=d.montant_souhaite, motif=d.motif, statut=d.statut, date_creation=d.date_creation,
        )

    d = DemandeCreditDB(
        id=str(uuid.uuid4())[:8], client_id=client.id, boutique_id=payload.boutique_id,
        montant_souhaite=payload.montant_souhaite, motif=payload.motif, statut=StatutDemandeCredit.en_attente,
        created_by=f"{client.nom} (appli mobile client)", updated_by=f"{client.nom} (appli mobile client)",
    )
    db.add(d)
    log_audit(
        db, f"Demande de crédit — {client.nom} ({client.contact}) — {payload.montant_souhaite:,.0f} GNF".replace(",", " "),
        client.nom, payload.boutique_id,
    )
    notifier_gerants_boutique(
        db, payload.boutique_id,
        f"Nouvelle demande de crédit de {client.nom} ({client.contact}) — {payload.montant_souhaite:,.0f} GNF. "
        f"Motif : {payload.motif} — KFSTORE".replace(",", " "),
        titre="Demande de crédit",
    )
    db.commit()
    db.refresh(d)
    return DemandeCredit(
        id=d.id, client_id=d.client_id, client_nom=client.nom, boutique_id=d.boutique_id,
        montant_souhaite=d.montant_souhaite, motif=d.motif, statut=d.statut, date_creation=d.date_creation,
    )


@router.post("/notifier-remboursement", response_model=MessageResponse)
def notifier_remboursement(
    payload: NotifierRemboursementRequest, client: ClientDB = Depends(get_current_client), db: Session = Depends(get_db)
) -> MessageResponse:
    """Ne crée jamais de remboursement réel — informe seulement la boutique, qui enregistre
    l'encaissement effectif (staff) après vérification des fonds réellement reçus."""
    dette = db.get(DetteDB, payload.dette_id)
    if not dette or dette.client_id != client.id:
        raise HTTPException(status_code=404, detail="Créance introuvable")
    if payload.montant <= 0:
        raise HTTPException(status_code=400, detail="Le montant doit être positif")

    log_audit(
        db, f"Client signale un remboursement — {client.nom} ({client.contact}) — "
        f"{payload.montant:,.0f} GNF sur créance #{dette.id}".replace(",", " "),
        client.nom, dette.boutique_id,
    )
    notifier_gerants_boutique(
        db, dette.boutique_id,
        f"{client.nom} ({client.contact}) signale avoir remboursé {payload.montant:,.0f} GNF sur sa créance "
        f"à {nom_boutique(db, dette.boutique_id)} (mode : {payload.mode_paiement.value})."
        + (f" Note : {payload.note}" if payload.note else "")
        + " Vérifiez et enregistrez l'encaissement réel avant de le prendre en compte. — KFSTORE".replace(",", " "),
        titre="Remboursement signalé",
    )
    db.commit()
    return MessageResponse(message="La boutique a été prévenue et vérifiera votre remboursement.")
