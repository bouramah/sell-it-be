import re

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import UTILISATEURS_GESTION
from app.core.security import get_current_user
from app.db_models.models import PermissionDB, RoleDB, UtilisateurDB
from app.models.schemas import DroitAcces, RoleInfo
from app.models.write_schemas import RoleCreate, RoleUpdate
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/roles", tags=["roles"])

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
PORTEES_VALIDES = ("boutique", "reseau")


@router.get("", response_model=list[RoleInfo])
def list_roles(db: Session = Depends(get_db)) -> list[RoleDB]:
    return db.query(RoleDB).order_by(RoleDB.ordre).all()


@router.post("", response_model=RoleInfo, status_code=201)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> RoleDB:
    require_permission(db, current_user, UTILISATEURS_GESTION)
    if not ID_PATTERN.match(payload.id):
        raise HTTPException(
            status_code=400,
            detail="L'identifiant doit être en minuscules, commencer par une lettre, et ne contenir que lettres/chiffres/underscore.",
        )
    if payload.portee not in PORTEES_VALIDES:
        raise HTTPException(status_code=400, detail="Portée invalide (attendu : boutique ou reseau)")
    if db.get(RoleDB, payload.id):
        raise HTTPException(status_code=409, detail="Un rôle avec cet identifiant existe déjà")

    ordre_max = db.query(RoleDB).count()
    role = RoleDB(id=payload.id, libelle=payload.libelle, portee=payload.portee, ordre=ordre_max, systeme=False)
    db.add(role)
    db.flush()  # la ligne roles doit exister avant les inserts permissions (FK fk_permissions_role)

    # Nouvelle ligne "aucun" pour chaque action déjà connue de la matrice, pour que ce
    # nouveau rôle apparaisse immédiatement dans toutes les lignes existantes — cf. CDC
    # §3.3 : un rôle personnalisé doit être utilisable "sans développement supplémentaire".
    actions = db.query(PermissionDB.module_action, PermissionDB.ordre).distinct().all()
    for module_action, ordre in actions:
        db.add(PermissionDB(module_action=module_action, role=payload.id, droit=DroitAcces.aucun, ordre=ordre))

    log_audit(db, f"Création rôle — {payload.libelle} ({payload.id})", f"{current_user.prenom} {current_user.nom}")
    db.commit()
    db.refresh(role)
    return role


@router.put("/{role_id}", response_model=RoleInfo)
def update_role(
    role_id: str,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> RoleDB:
    require_permission(db, current_user, UTILISATEURS_GESTION)
    role = db.get(RoleDB, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Rôle introuvable")
    if payload.portee is not None and payload.portee not in PORTEES_VALIDES:
        raise HTTPException(status_code=400, detail="Portée invalide (attendu : boutique ou reseau)")
    if role.systeme and payload.portee is not None and payload.portee != role.portee:
        raise HTTPException(status_code=400, detail="La portée d'un rôle système ne peut pas être modifiée.")

    if payload.libelle is not None:
        role.libelle = payload.libelle
    if payload.portee is not None:
        role.portee = payload.portee

    log_audit(db, f"Modification rôle — {role.libelle} ({role.id})", f"{current_user.prenom} {current_user.nom}")
    db.commit()
    db.refresh(role)
    return role


@router.delete("/{role_id}", status_code=204)
def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, UTILISATEURS_GESTION)
    role = db.get(RoleDB, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Rôle introuvable")
    if role.systeme:
        raise HTTPException(status_code=400, detail="Ce rôle est un rôle système et ne peut pas être supprimé.")
    if db.query(UtilisateurDB).filter(UtilisateurDB.role == role_id).count() > 0:
        raise HTTPException(status_code=409, detail="Ce rôle est encore attribué à des utilisateurs.")

    db.query(PermissionDB).filter(PermissionDB.role == role_id).delete()
    log_audit(db, f"Suppression rôle — {role.libelle} ({role.id})", f"{current_user.prenom} {current_user.nom}")
    db.delete(role)
    db.commit()
