from sqlalchemy.orm import Session

from app.db_models.models import ParametreSecuriteDB


def parametre_actif(db: Session, parametre_id: str, defaut: bool = True) -> bool:
    """Lit un interrupteur de la page Sécurité (table parametres_securite) — permet à
    l'administrateur d'activer/désactiver un contrôle (verrouillage, 2FA, double
    validation...) sans développement, cf. CDC §7.2/§7.3."""
    p = db.get(ParametreSecuriteDB, parametre_id)
    return p.actif if p else defaut
