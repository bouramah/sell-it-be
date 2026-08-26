"""TVA — les prix enregistrés dans KFSTORE sont TTC (prix affiché = prix payé,
cf. décision produit) ; ce module ne recalcule donc jamais un prix, il se contente
d'en extraire la ventilation HT / TVA pour l'affichage sur les documents
commerciaux (facture, reçu, bons de commande/réception). Taux et application
configurables (ParametreFiscalDB) — cf. écran Paramètres, pas codés en dur."""
from sqlalchemy.orm import Session

from app.db_models.models import ParametreFiscalDB

TAUX_TVA_DEFAUT = 0.18


def get_parametre_fiscal(db: Session) -> ParametreFiscalDB:
    p = db.get(ParametreFiscalDB, "tva")
    if not p:
        p = ParametreFiscalDB(id="tva", taux=TAUX_TVA_DEFAUT, actif=True, created_by="Système", updated_by="Système")
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


def ventilation_tva(montant_ttc: float, taux: float) -> tuple[float, float]:
    """Renvoie (montant_ht, montant_tva) à partir d'un montant TTC."""
    montant_ht = montant_ttc / (1 + taux)
    return montant_ht, montant_ttc - montant_ht
