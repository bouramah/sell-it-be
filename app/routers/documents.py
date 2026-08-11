from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, Response
from app.core.authorization import assert_boutique_access
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import (
    BoutiqueDB,
    ClientDB,
    CommandeClientDB,
    CommandeFournisseurDB,
    FournisseurDB,
    PaiementClientDB,
    ProduitDB,
    UtilisateurDB,
)
from app.services.pdf import articles_table, document_shell, render_pdf, totals_block

router = APIRouter(prefix="/api/v1", tags=["documents"])

STATUT_COMMANDE_CLIENT_LABELS = {
    "en_attente": "En attente", "confirmee": "Confirmée", "en_preparation": "En préparation",
    "en_livraison": "En livraison", "livree": "Livrée", "annulee": "Annulée",
}
STATUT_COMMANDE_FOURNISSEUR_LABELS = {
    "brouillon": "Brouillon", "validee": "Validée", "envoyee": "Envoyée",
    "receptionnee_partielle": "Réceptionnée (partielle)", "receptionnee": "Réceptionnée", "cloturee": "Clôturée",
}
STATUT_PAIEMENT_LABELS = {
    "encaisse": "Encaissé", "en_attente": "En attente", "paye": "Payé", "partiel": "Partiel",
}


def _gnf(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", " ") + " GNF"


def _pdf_response(pdf_bytes: bytes, filename: str) -> Response:
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/commandes-fournisseurs/{commande_id}/bon-commande.pdf")
def bon_commande_pdf(
    commande_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Response:
    c = db.get(CommandeFournisseurDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    assert_boutique_access(current_user, c.boutique_id)
    fournisseur = db.get(FournisseurDB, c.fournisseur_id)
    boutique = db.get(BoutiqueDB, c.boutique_id)
    produits = {p.id: p for p in db.query(ProduitDB).all()}

    rows = [
        {
            "produit": produits[l.produit_id].nom if l.produit_id in produits else l.produit_id,
            "quantite": l.quantite,
            "prix_unitaire": _gnf(l.prix_unitaire),
            "sous_total": _gnf(l.quantite * l.prix_unitaire),
        }
        for l in c.lignes
    ]

    body = articles_table(rows) + totals_block(
        [], "Montant total de la commande", _gnf(c.montant)
    )

    html = document_shell(
        doc_title="Bon de commande",
        reference=f"#{c.id}",
        date_str=f"Livraison attendue le {c.date_attendue.strftime('%d/%m/%Y')}",
        statut_label=STATUT_COMMANDE_FOURNISSEUR_LABELS.get(c.statut, str(c.statut)),
        de_label="Émis par",
        de_lignes=[
            "KFSTORE — GROUPE SKF SARL",
            boutique.nom if boutique else c.boutique_id,
            f"{boutique.quartier}, {boutique.commune}, {boutique.ville}" if boutique else "",
            f"Tél : {boutique.telephone}" if boutique else "",
        ],
        a_label="Fournisseur",
        a_lignes=[
            fournisseur.nom if fournisseur else c.fournisseur_id,
            f"Contact : {fournisseur.contact}" if fournisseur else "",
            f"Conditions de paiement : {fournisseur.conditions_paiement}" if fournisseur else "",
        ],
        body_html=body if rows else "<p>Aucun article enregistré pour cette commande.</p>",
        signatures=("Signature responsable achats KFSTORE", "Signature et cachet fournisseur"),
    )
    return _pdf_response(render_pdf(html), f"bon-commande-{c.id}.pdf")


@router.get("/commandes-fournisseurs/{commande_id}/bon-reception.pdf")
def bon_reception_pdf(
    commande_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Response:
    c = db.get(CommandeFournisseurDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    assert_boutique_access(current_user, c.boutique_id)
    fournisseur = db.get(FournisseurDB, c.fournisseur_id)
    boutique = db.get(BoutiqueDB, c.boutique_id)
    produits = {p.id: p for p in db.query(ProduitDB).all()}

    rows = [
        {
            "produit": produits[l.produit_id].nom if l.produit_id in produits else l.produit_id,
            "quantite": l.quantite,
            "extra": l.quantite_recue,
            "prix_unitaire": _gnf(l.prix_unitaire),
            "sous_total": _gnf(l.quantite_recue * l.prix_unitaire),
        }
        for l in c.lignes
    ]
    valeur_recue = sum(l.quantite_recue * l.prix_unitaire for l in c.lignes)

    body = articles_table(rows, montant_col_label="Valeur reçue", extra_col="Quantité reçue") + totals_block(
        [("Montant total commandé", _gnf(c.montant))], "Valeur totale reçue à ce jour", _gnf(valeur_recue)
    )

    html = document_shell(
        doc_title="Bon de réception",
        reference=f"#{c.id}",
        date_str=f"Réceptionné le {c.date_reception.strftime('%d/%m/%Y')}" if c.date_reception else "Réception en cours",
        statut_label=STATUT_COMMANDE_FOURNISSEUR_LABELS.get(c.statut, str(c.statut)),
        de_label="Boutique réceptrice",
        de_lignes=[
            boutique.nom if boutique else c.boutique_id,
            f"{boutique.quartier}, {boutique.commune}, {boutique.ville}" if boutique else "",
            f"Tél : {boutique.telephone}" if boutique else "",
        ],
        a_label="Fournisseur",
        a_lignes=[
            fournisseur.nom if fournisseur else c.fournisseur_id,
            f"Contact : {fournisseur.contact}" if fournisseur else "",
        ],
        body_html=body if rows else "<p>Aucun article enregistré pour cette commande.</p>",
        signatures=("Signature magasinier KFSTORE", "Signature livreur / transporteur"),
    )
    return _pdf_response(render_pdf(html), f"bon-reception-{c.id}.pdf")


@router.get("/commandes-clients/{commande_id}/facture.pdf")
def facture_pdf(
    commande_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Response:
    c = db.get(CommandeClientDB, commande_id)
    if not c:
        raise HTTPException(status_code=404, detail="Commande introuvable")
    assert_boutique_access(current_user, c.boutique_id)
    boutique = db.get(BoutiqueDB, c.boutique_id)
    client = db.query(ClientDB).filter(ClientDB.nom == c.client_nom).first()
    produits = {p.id: p for p in db.query(ProduitDB).all()}

    rows = [
        {
            "produit": produits[l.produit_id].nom if l.produit_id in produits else l.produit_id,
            "quantite": l.quantite,
            "prix_unitaire": _gnf(l.prix_unitaire),
            "sous_total": _gnf(l.quantite * l.prix_unitaire),
        }
        for l in c.lignes
    ]

    body = articles_table(rows) + totals_block([], "Montant total à payer", _gnf(c.montant))

    html = document_shell(
        doc_title="Facture",
        reference=f"#{c.id}",
        date_str=c.date_creation.strftime("%d/%m/%Y"),
        statut_label=STATUT_COMMANDE_CLIENT_LABELS.get(c.statut, str(c.statut)),
        de_label="Vendeur",
        de_lignes=[
            "KFSTORE — GROUPE SKF SARL",
            boutique.nom if boutique else c.boutique_id,
            f"{boutique.quartier}, {boutique.commune}, {boutique.ville}" if boutique else "",
            f"Tél : {boutique.telephone}" if boutique else "",
        ],
        a_label="Client",
        a_lignes=[
            c.client_nom,
            f"Contact : {client.contact}" if client else "",
        ],
        body_html=body if rows else "<p>Aucun article enregistré pour cette commande.</p>",
        signatures=("Cachet et signature KFSTORE", "Signature client"),
    )
    return _pdf_response(render_pdf(html), f"facture-{c.id}.pdf")


@router.get("/paiements-clients/{paiement_id}/recu.pdf")
def recu_pdf(
    paiement_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Response:
    p = db.get(PaiementClientDB, paiement_id)
    if not p:
        raise HTTPException(status_code=404, detail="Paiement introuvable")
    assert_boutique_access(current_user, p.boutique_id)
    boutique = db.get(BoutiqueDB, p.boutique_id)

    body = f"""
    <div style="margin: 30px 0; padding: 24px; background: #f0fdfa; border-radius: 8px; text-align: center;">
      <div style="font-size: 9pt; text-transform: uppercase; letter-spacing: 0.08em; color: #0f766e;">Montant reçu</div>
      <div style="font-size: 28pt; font-weight: bold; color: #0f766e; margin-top: 6px;">{_gnf(p.montant)}</div>
    </div>
    <table class="articles">
      <tbody>
        <tr><td>Référence</td><td class="num">{p.reference}</td></tr>
        <tr><td>Mode de paiement</td><td class="num">{p.mode_paiement.value.replace('_', ' ').title()}</td></tr>
        <tr><td>Date</td><td class="num">{p.date.strftime('%d/%m/%Y')}</td></tr>
        <tr><td>Statut</td><td class="num">{STATUT_PAIEMENT_LABELS.get(p.statut, str(p.statut))}</td></tr>
      </tbody>
    </table>
    """

    html = document_shell(
        doc_title="Reçu de paiement",
        reference=f"#{p.id}",
        date_str=p.date.strftime("%d/%m/%Y"),
        statut_label=None,
        de_label="Émis par",
        de_lignes=[
            "KFSTORE — GROUPE SKF SARL",
            boutique.nom if boutique else p.boutique_id,
            f"Tél : {boutique.telephone}" if boutique else "",
        ],
        a_label="Client",
        a_lignes=[p.client_nom],
        body_html=body,
        signatures=("Cachet et signature KFSTORE", "Signature client"),
    )
    return _pdf_response(render_pdf(html), f"recu-{p.id}.pdf")
