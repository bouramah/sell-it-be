import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.core.security import DEFAULT_PASSWORD, get_current_user, hash_password
from app.core.authorization import require_permission
from app.core.module_actions import UTILISATEURS_GESTION
from app.db_models.models import BoutiqueDB, PermissionDB, RoleDB, UtilisateurDB
from app.models.schemas import PermissionLigne, Utilisateur
from app.models.write_schemas import PermissionUpdate, UtilisateurCreate, UtilisateurUpdate
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1", tags=["utilisateurs"])


def _to_schema(u: UtilisateurDB) -> Utilisateur:
    return Utilisateur(
        id=u.id,
        nom=u.nom,
        prenom=u.prenom,
        contact=u.contact,
        role=u.role,
        boutique_ids=[b.id for b in u.boutiques],
        statut=u.statut,
        derniere_connexion=u.derniere_connexion,
    )


@router.get("/utilisateurs", response_model=list[Utilisateur])
def list_utilisateurs(role: str | None = None, boutique_id: str | None = None, db: Session = Depends(get_db)) -> list[Utilisateur]:
    query = db.query(UtilisateurDB)
    if role:
        query = query.filter(UtilisateurDB.role == role)
    result = [_to_schema(u) for u in query.all()]
    if boutique_id:
        result = [u for u in result if boutique_id in u.boutique_ids]
    return result


@router.post("/utilisateurs", response_model=Utilisateur, status_code=201)
def create_utilisateur(
    payload: UtilisateurCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Utilisateur:
    require_permission(db, current_user, UTILISATEURS_GESTION)
    if db.query(UtilisateurDB).filter(UtilisateurDB.contact == payload.contact).first():
        raise HTTPException(status_code=409, detail="Un utilisateur avec ce contact existe déjà")
    if not db.get(RoleDB, payload.role):
        raise HTTPException(status_code=404, detail="Rôle introuvable")

    boutiques = db.query(BoutiqueDB).filter(BoutiqueDB.id.in_(payload.boutique_ids)).all()
    u = UtilisateurDB(
        id=str(uuid.uuid4())[:8],
        nom=payload.nom,
        prenom=payload.prenom,
        contact=payload.contact,
        mot_de_passe_hash=hash_password(payload.mot_de_passe or DEFAULT_PASSWORD),
        role=payload.role,
        statut=payload.statut,
        boutiques=boutiques,
    )
    db.add(u)
    log_audit(db, f"Création utilisateur — {payload.prenom} {payload.nom} ({payload.role})", f"{current_user.prenom} {current_user.nom}")
    db.commit()
    db.refresh(u)
    return _to_schema(u)


@router.put("/utilisateurs/{utilisateur_id}", response_model=Utilisateur)
def update_utilisateur(
    utilisateur_id: str,
    payload: UtilisateurUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Utilisateur:
    require_permission(db, current_user, UTILISATEURS_GESTION)
    u = db.get(UtilisateurDB, utilisateur_id)
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if payload.role is not None and not db.get(RoleDB, payload.role):
        raise HTTPException(status_code=404, detail="Rôle introuvable")

    ancien_role, ancien_statut = u.role, u.statut
    data = payload.model_dump(exclude_unset=True, exclude={"mot_de_passe", "boutique_ids"})
    for field, value in data.items():
        setattr(u, field, value)

    if payload.mot_de_passe:
        u.mot_de_passe_hash = hash_password(payload.mot_de_passe)
    if payload.boutique_ids is not None:
        u.boutiques = db.query(BoutiqueDB).filter(BoutiqueDB.id.in_(payload.boutique_ids)).all()

    auteur = f"{current_user.prenom} {current_user.nom}"
    if payload.role is not None and payload.role != ancien_role:
        log_audit(db, f"Modification des droits — {u.prenom} {u.nom} passé en {payload.role}", auteur)
    if payload.statut is not None and payload.statut != ancien_statut:
        log_audit(db, f"Compte {'activé' if payload.statut == 'actif' else 'désactivé'} — {u.prenom} {u.nom}", auteur)

    db.commit()
    db.refresh(u)
    return _to_schema(u)


@router.delete("/utilisateurs/{utilisateur_id}", status_code=204)
def delete_utilisateur(
    utilisateur_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, UTILISATEURS_GESTION)
    u = db.get(UtilisateurDB, utilisateur_id)
    if not u:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    log_audit(db, f"Suppression utilisateur — {u.prenom} {u.nom}", f"{current_user.prenom} {current_user.nom}")
    db.delete(u)
    db.commit()


@router.get("/permissions", response_model=list[PermissionLigne])
def get_permissions(db: Session = Depends(get_db)) -> list[PermissionLigne]:
    rows = db.query(PermissionDB).order_by(PermissionDB.ordre).all()
    lignes: dict[str, dict[str, str]] = {}
    for r in rows:
        lignes.setdefault(r.module_action, {})[r.role] = r.droit
    return [PermissionLigne(module_action=module_action, droits=droits) for module_action, droits in lignes.items()]


@router.put("/permissions", response_model=PermissionLigne)
def update_permission(
    payload: PermissionUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> PermissionLigne:
    require_permission(db, current_user, UTILISATEURS_GESTION)
    row = db.get(PermissionDB, (payload.module_action, payload.role))
    if not row:
        raise HTTPException(status_code=404, detail="Permission introuvable")
    row.droit = payload.droit
    log_audit(
        db,
        f"Matrice des droits — {payload.module_action} / {payload.role} → {payload.droit.value}",
        f"{current_user.prenom} {current_user.nom}",
    )
    db.commit()

    rows = db.query(PermissionDB).filter(PermissionDB.module_action == payload.module_action).all()
    droits = {r.role: r.droit for r in rows}
    return PermissionLigne(module_action=payload.module_action, droits=droits)
