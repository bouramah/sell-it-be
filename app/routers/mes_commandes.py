"""Commandes de l'appli mobile client — CDC §3.5 : passage de commande depuis l'appli mobile
client (canal "mobile_client"), suivi en temps réel, historique et facture téléchargeable.
Strictement scopé au client authentifié (get_current_client) — un client ne peut jamais voir
ni créer une commande pour un autre client."""
from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, Response
from app.core.database import get_db
from app.core.security import get_current_client
from app.db_models.models import BoutiqueDB, ClientDB, CommandeClientDB
from app.models.schemas import CanalCommande, CommandeClient, CommandeClientDetail, ModePaiement, StatutBoutique, StatutCommandeClient
from app.models.write_schemas import ArticleCommandeInput, CommandeClientCreate
from app.routers.commandes import _serialiser_commande_client, creer_commande_client
from app.routers.documents import generer_facture_pdf

router = APIRouter(prefix="/api/v1/mes-commandes", tags=["mes-commandes"])


class MaCommandeCreate(BaseModel):
    boutique_id: str
    mode_paiement: ModePaiement
    articles: list[ArticleCommandeInput]


@router.get("", response_model=list[CommandeClient])
def mes_commandes(client: ClientDB = Depends(get_current_client), db: Session = Depends(get_db)) -> list[CommandeClientDB]:
    return (
        db.query(CommandeClientDB)
        .filter(CommandeClientDB.client_id == client.id)
        .order_by(CommandeClientDB.date_creation.desc())
        .all()
    )


@router.get("/{commande_id}", response_model=CommandeClientDetail)
def ma_commande(
    commande_id: str, client: ClientDB = Depends(get_current_client), db: Session = Depends(get_db)
) -> CommandeClientDetail:
    c = db.get(CommandeClientDB, commande_id)
    if not c or c.client_id != client.id:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    return _serialiser_commande_client(db, c)


@router.get("/{commande_id}/facture.pdf")
def ma_facture(commande_id: str, client: ClientDB = Depends(get_current_client), db: Session = Depends(get_db)) -> Response:
    c = db.get(CommandeClientDB, commande_id)
    if not c or c.client_id != client.id:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    return generer_facture_pdf(db, c)


@router.post("", response_model=CommandeClientDetail, status_code=201)
def creer_ma_commande(
    payload: MaCommandeCreate, client: ClientDB = Depends(get_current_client), db: Session = Depends(get_db)
) -> CommandeClientDetail:
    if payload.mode_paiement == ModePaiement.mobile_money:
        raise HTTPException(status_code=400, detail="Le paiement Mobile Money n'est pas encore disponible.")
    if payload.mode_paiement == ModePaiement.credit_client and not client.credit_autorise:
        raise HTTPException(
            status_code=403,
            detail="Vous n'avez pas de droit de crédit actif sur ce compte. Contactez la boutique pour l'activer.",
        )
    boutique = db.get(BoutiqueDB, payload.boutique_id)
    if not boutique or boutique.statut != StatutBoutique.active:
        raise HTTPException(status_code=404, detail="Boutique introuvable ou fermée")

    create_payload = CommandeClientCreate(
        client_nom=client.nom, client_id=client.id, boutique_id=payload.boutique_id,
        canal=CanalCommande.mobile_client, mode_paiement=payload.mode_paiement,
        statut=StatutCommandeClient.en_attente, articles=payload.articles,
    )
    c = creer_commande_client(db, create_payload, f"{client.nom} (appli mobile client)")
    return _serialiser_commande_client(db, c)
