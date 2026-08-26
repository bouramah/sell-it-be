import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import a_portee_reseau, assert_boutique_access, boutiques_autorisees, require_permission
from app.core.database import get_db
from app.core.db_errors import commit_or_409
from app.core.module_actions import BOUTIQUE_GESTION, FOURNISSEUR_GESTION
from app.core.security import get_current_user
from app.db_models.models import BoutiqueDB, BoutiqueSecteurDB, CommandeFournisseurDB, FournisseurDB, UtilisateurDB
from app.models.schemas import Boutique, Fournisseur, StatutBoutique, StatutCommandeFournisseur, TopFournisseur
from app.models.write_schemas import BoutiqueCreate, BoutiqueUpdate, FournisseurCreate, FournisseurUpdate
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1", tags=["reseau"])


def _to_schema(b: BoutiqueDB) -> Boutique:
    return Boutique(
        id=b.id,
        nom=b.nom,
        secteurs=[s.secteur for s in b.secteurs],
        quartier=b.quartier,
        commune=b.commune,
        ville=b.ville,
        horaires=b.horaires,
        responsable=b.responsable,
        statut=b.statut,
        telephone=b.telephone,
        latitude=b.latitude,
        longitude=b.longitude,
        secteur_geo_id=b.secteur_geo_id,
    )


@router.get("/boutiques", response_model=list[Boutique])
def list_boutiques(
    ville: str | None = None,
    secteur: str | None = None,
    statut: StatutBoutique | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[Boutique]:
    query = db.query(BoutiqueDB)
    if ville:
        query = query.filter(BoutiqueDB.ville == ville)
    if statut:
        query = query.filter(BoutiqueDB.statut == statut)
    if not a_portee_reseau(current_user):
        query = query.filter(BoutiqueDB.id.in_(boutiques_autorisees(current_user)))
    result = [_to_schema(b) for b in query.all()]
    if secteur:
        result = [b for b in result if secteur in b.secteurs]
    return result


@router.get("/boutiques/{boutique_id}", response_model=Boutique)
def get_boutique(
    boutique_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Boutique:
    b = db.get(BoutiqueDB, boutique_id)
    if not b:
        raise HTTPException(status_code=404, detail="Boutique introuvable")
    assert_boutique_access(current_user, boutique_id)
    return _to_schema(b)


@router.post("/boutiques", response_model=Boutique, status_code=201)
def create_boutique(
    payload: BoutiqueCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Boutique:
    require_permission(db, current_user, BOUTIQUE_GESTION)
    boutique_id = str(uuid.uuid4())[:8]
    auteur = f"{current_user.prenom} {current_user.nom}"
    b = BoutiqueDB(
        id=boutique_id,
        nom=payload.nom,
        quartier=payload.quartier,
        commune=payload.commune,
        ville=payload.ville,
        horaires=payload.horaires,
        responsable=payload.responsable,
        statut=payload.statut,
        telephone=payload.telephone,
        latitude=payload.latitude,
        longitude=payload.longitude,
        secteur_geo_id=payload.secteur_geo_id,
        created_by=auteur,
        updated_by=auteur,
    )
    b.secteurs = [BoutiqueSecteurDB(boutique_id=boutique_id, secteur=s) for s in payload.secteurs]
    db.add(b)
    log_audit(db, f"Création boutique — {payload.nom}", auteur, boutique_id)
    db.commit()
    db.refresh(b)
    return _to_schema(b)


@router.put("/boutiques/{boutique_id}", response_model=Boutique)
def update_boutique(
    boutique_id: str,
    payload: BoutiqueUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> Boutique:
    require_permission(db, current_user, BOUTIQUE_GESTION)
    b = db.get(BoutiqueDB, boutique_id)
    if not b:
        raise HTTPException(status_code=404, detail="Boutique introuvable")

    data = payload.model_dump(exclude_unset=True, exclude={"secteurs"})
    for field, value in data.items():
        setattr(b, field, value)

    if payload.secteurs is not None:
        b.secteurs = [BoutiqueSecteurDB(boutique_id=boutique_id, secteur=s) for s in payload.secteurs]

    b.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(b)
    return _to_schema(b)


@router.delete("/boutiques/{boutique_id}", status_code=204)
def delete_boutique(
    boutique_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, BOUTIQUE_GESTION)
    b = db.get(BoutiqueDB, boutique_id)
    if not b:
        raise HTTPException(status_code=404, detail="Boutique introuvable")
    # boutique_id volontairement omis : la boutique référencée n'existera plus après ce commit.
    log_audit(db, f"Suppression boutique — {b.nom}", f"{current_user.prenom} {current_user.nom}")
    db.delete(b)
    commit_or_409(db, "Impossible de supprimer cette boutique : des données (stock, commandes, caisses…) y sont encore rattachées.")


@router.get("/fournisseurs", response_model=list[Fournisseur])
def list_fournisseurs(secteur: str | None = None, db: Session = Depends(get_db)) -> list[FournisseurDB]:
    query = db.query(FournisseurDB)
    if secteur:
        query = query.filter(FournisseurDB.secteur == secteur)
    return query.all()


@router.get("/fournisseurs/top", response_model=list[TopFournisseur])
def top_fournisseurs(
    boutique_id: str | None = None,
    limite: int = 10,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[TopFournisseur]:
    """Classement des fournisseurs par montant d'achats réceptionnés — tableau de bord
    comparatif fournisseurs (CDC demande client). Ne compte que les réceptions effectives,
    même convention que la comptabilité (achats = commandes réceptionnées/clôturées)."""
    query = db.query(CommandeFournisseurDB).filter(
        CommandeFournisseurDB.statut.in_([StatutCommandeFournisseur.receptionnee, StatutCommandeFournisseur.cloturee])
    )
    if boutique_id:
        assert_boutique_access(current_user, boutique_id)
        query = query.filter(CommandeFournisseurDB.boutique_id == boutique_id)
    elif not a_portee_reseau(current_user):
        query = query.filter(CommandeFournisseurDB.boutique_id.in_(boutiques_autorisees(current_user)))
    commandes = query.all()

    fournisseurs_by_id = {f.id: f.nom for f in db.query(FournisseurDB).all()}
    agrege: dict[str, dict] = {}
    for c in commandes:
        entry = agrege.setdefault(c.fournisseur_id, {"montant": 0.0, "nb": 0})
        entry["montant"] += c.montant
        entry["nb"] += 1

    classement = sorted(agrege.items(), key=lambda kv: kv[1]["montant"], reverse=True)[:limite]
    return [
        TopFournisseur(
            fournisseur_id=fid, fournisseur_nom=fournisseurs_by_id.get(fid, fid),
            montant_achats=entry["montant"], nombre_commandes=entry["nb"],
        )
        for fid, entry in classement
    ]


@router.post("/fournisseurs", response_model=Fournisseur, status_code=201)
def create_fournisseur(
    payload: FournisseurCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> FournisseurDB:
    require_permission(db, current_user, FOURNISSEUR_GESTION)
    auteur = f"{current_user.prenom} {current_user.nom}"
    f = FournisseurDB(id=str(uuid.uuid4())[:8], created_by=auteur, updated_by=auteur, **payload.model_dump())
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


@router.put("/fournisseurs/{fournisseur_id}", response_model=Fournisseur)
def update_fournisseur(
    fournisseur_id: str,
    payload: FournisseurUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> FournisseurDB:
    require_permission(db, current_user, FOURNISSEUR_GESTION)
    f = db.get(FournisseurDB, fournisseur_id)
    if not f:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(f, field, value)
    f.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(f)
    return f


@router.delete("/fournisseurs/{fournisseur_id}", status_code=204)
def delete_fournisseur(
    fournisseur_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, FOURNISSEUR_GESTION)
    f = db.get(FournisseurDB, fournisseur_id)
    if not f:
        raise HTTPException(status_code=404, detail="Fournisseur introuvable")
    db.delete(f)
    commit_or_409(db, "Impossible de supprimer ce fournisseur : des commandes y sont encore rattachées.")
