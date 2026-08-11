from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends
from app.core.authorization import ROLES_PORTEE_RESEAU, require_role
from app.core.database import get_db
from app.core.security import get_current_user
from app.db_models.models import BoutiqueDB, CommandeClientDB, CommandeFournisseurDB, DepenseDB, UtilisateurDB
from app.models.schemas import CompteResultatBoutique, StatutCommandeClient, StatutCommandeFournisseur

router = APIRouter(prefix="/api/v1/comptabilite", tags=["comptabilite"])


class ComptabiliteConsolidee(BaseModel):
    ca_consolide: float
    marge_nette_consolidee: float
    depenses_consolidees: float
    marge_nette_moyenne_pct: float
    comptes: list[CompteResultatBoutique]


@router.get("", response_model=ComptabiliteConsolidee)
def get_comptabilite(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ComptabiliteConsolidee:
    # Comptabilité consolidée du réseau — réservée au siège (cf. CDC).
    require_role(current_user, *ROLES_PORTEE_RESEAU)
    boutiques = db.query(BoutiqueDB).all()

    commandes_clients = db.query(CommandeClientDB).filter(CommandeClientDB.statut != StatutCommandeClient.annulee).all()
    commandes_fournisseurs = db.query(CommandeFournisseurDB).filter(
        CommandeFournisseurDB.statut.in_([StatutCommandeFournisseur.receptionnee, StatutCommandeFournisseur.cloturee])
    ).all()
    depenses = db.query(DepenseDB).all()

    comptes = []
    for b in boutiques:
        ca = sum(c.montant for c in commandes_clients if c.boutique_id == b.id)
        achats = sum(c.montant for c in commandes_fournisseurs if c.boutique_id == b.id)
        dep = sum(d.montant for d in depenses if d.boutique_id == b.id)
        comptes.append(CompteResultatBoutique(
            boutique_id=b.id, chiffre_affaires=ca, achats=achats, depenses=dep, marge_nette=ca - achats - dep,
        ))

    ca_total = sum(c.chiffre_affaires for c in comptes)
    marge_total = sum(c.marge_nette for c in comptes)
    depenses_total = sum(c.depenses for c in comptes)

    return ComptabiliteConsolidee(
        ca_consolide=ca_total,
        marge_nette_consolidee=marge_total,
        depenses_consolidees=depenses_total,
        marge_nette_moyenne_pct=round((marge_total / ca_total) * 100, 1) if ca_total else 0,
        comptes=comptes,
    )
