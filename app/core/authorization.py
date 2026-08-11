"""Authorization helpers enforcing the CDC's role/boutique scoping rules (§3.3, §7.2, §11).

Critère d'acceptation #1 : "Un vendeur ou caissier ne peut, en aucun cas, consulter ou
modifier les données d'une boutique à laquelle il n'est pas rattaché."
Critère d'acceptation #2 : "L'administrateur peut consulter et agir sur l'ensemble des
boutiques sans restriction."

Rôles à portée réseau (accès à toutes les boutiques) : administrateur, responsable_achats.
Rôles à portée boutique (limités à leurs boutiques de rattachement) : vendeur, caissier, gérant.
"""
from fastapi import HTTPException

from app.db_models.models import UtilisateurDB
from app.models.schemas import Role

ROLES_PORTEE_RESEAU = {Role.administrateur, Role.responsable_achats}


def a_portee_reseau(user: UtilisateurDB) -> bool:
    return user.role in ROLES_PORTEE_RESEAU


def boutiques_autorisees(user: UtilisateurDB) -> set[str]:
    """Ensemble des boutique_id auxquelles cet utilisateur a accès. None (portée réseau)
    n'est pas représentable ici — utiliser a_portee_reseau() pour ce cas avant d'appeler."""
    return {b.id for b in user.boutiques}


def assert_boutique_access(user: UtilisateurDB, boutique_id: str | None) -> None:
    """Lève 403 si l'utilisateur n'a pas la portée réseau et que boutique_id n'est pas
    parmi ses boutiques de rattachement. boutique_id=None (opération non rattachée à une
    boutique précise) est autorisé pour tout utilisateur authentifié."""
    if boutique_id is None:
        return
    if a_portee_reseau(user):
        return
    if boutique_id not in boutiques_autorisees(user):
        raise HTTPException(status_code=403, detail="Vous n'avez pas accès à cette boutique")


def filtre_boutiques(user: UtilisateurDB, boutique_id: str | None) -> str | list[str] | None:
    """Pour les endpoints de liste : renvoie le filtre boutique_id effectif à appliquer.
    - Portée réseau : renvoie boutique_id tel quel (filtre optionnel du siège, ou None = tout voir).
    - Portée boutique : si boutique_id précisé, vérifie l'accès puis le renvoie ; sinon,
      renvoie la liste de ses boutiques (jamais None, pour ne jamais montrer tout le réseau)."""
    if a_portee_reseau(user):
        return boutique_id
    if boutique_id is not None:
        assert_boutique_access(user, boutique_id)
        return boutique_id
    return list(boutiques_autorisees(user))


def apply_boutique_filter(query, column, user: UtilisateurDB, boutique_id: str | None):
    """Applique le filtre boutique_id calculé par filtre_boutiques() à une requête
    SQLAlchemy, sur la colonne boutique_id passée en paramètre."""
    filtre = filtre_boutiques(user, boutique_id)
    if filtre is None:
        return query
    if isinstance(filtre, list):
        return query.filter(column.in_(filtre))
    return query.filter(column == filtre)


def require_role(user: UtilisateurDB, *roles: Role) -> None:
    if user.role not in roles:
        raise HTTPException(status_code=403, detail="Action réservée à un autre rôle")


def require_admin(user: UtilisateurDB) -> None:
    require_role(user, Role.administrateur)
