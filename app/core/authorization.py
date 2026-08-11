"""Authorization helpers enforcing the CDC's role/boutique scoping rules (§3.3, §7.2, §11).

Critère d'acceptation #1 : "Un vendeur ou caissier ne peut, en aucun cas, consulter ou
modifier les données d'une boutique à laquelle il n'est pas rattaché."
Critère d'acceptation #2 : "L'administrateur peut consulter et agir sur l'ensemble des
boutiques sans restriction."

Rôles à portée réseau (accès à toutes les boutiques) : administrateur, responsable_achats.
Rôles à portée boutique (limités à leurs boutiques de rattachement) : vendeur, caissier, gérant.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db_models.models import PermissionDB, UtilisateurDB
from app.models.schemas import DroitAcces, Role

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


def require_permission(db: Session, user: UtilisateurDB, *module_actions: str) -> None:
    """Vérifie que l'utilisateur a un droit non 'aucun' sur au moins une des actions
    données, en interrogeant en direct la matrice des droits (table `permissions`).

    C'est cette table — modifiable depuis Utilisateurs & droits, sans développement —
    qui fait foi pour l'autorisation, pas un rôle codé en dur (cf. CDC §3.3 : "cette
    matrice sera formalisée en base de données sous forme de permissions granulaires...
    afin de permettre la création de rôles personnalisés sans développement
    supplémentaire"). Plusieurs module_actions peuvent être passés quand une même route
    sert plusieurs lignes de la matrice (ex. comptabilité "de sa boutique" vs
    "consolidée du réseau") — l'accès est autorisé si l'une d'elles n'est pas 'aucun'.

    L'administrateur passe toujours, sans consulter la table : la matrice elle-même est
    modifiable uniquement par un administrateur (cf. "Gérer les droits utilisateurs"), donc
    si ce contournement n'existait pas, une ligne mal configurée (ex. administrateur → "Gérer
    les droits utilisateurs" → aucun) verrouillerait tout le monde hors de l'écran qui permet
    de la corriger. Conforme au critère d'acceptation #2 du CDC : "L'administrateur peut
    consulter et agir sur l'ensemble des boutiques sans restriction"."""
    if user.role == Role.administrateur:
        return
    rows = (
        db.query(PermissionDB)
        .filter(PermissionDB.module_action.in_(module_actions), PermissionDB.role == user.role)
        .all()
    )
    if not rows or all(r.droit == DroitAcces.aucun for r in rows):
        raise HTTPException(status_code=403, detail="Action non autorisée pour votre rôle")
