import uuid

from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import BAREME_CREDIT_BENEFICIAIRE_GESTION, REFERENTIELS_GESTION, SECURITE_GESTION
from app.core.security import get_current_user
from app.data.fixtures import REFERENTIELS
from app.db_models.models import BaremeCreditBeneficiaireDB, EtablissementDB, ParametreApplicationDB, ParametreFiscalDB, ReferentielDB, UtilisateurDB
from app.models.schemas import BaremeCreditBeneficiaire, ParametreApplication, ParametreFiscal, ReferentielItem
from app.models.write_schemas import BaremeCreditBeneficiaireCreate, ParametreApplicationUpdate, ParametreFiscalUpdate, ReferentielCreate, ReferentielUpdate
from app.services.audit import log_audit
from app.services.bareme_credit import verifier_chevauchement_bareme
from app.services.fiscalite import get_parametre_fiscal

router = APIRouter(prefix="/api/v1/parametres", tags=["parametres"])


@router.get("/application", response_model=list[ParametreApplication])
def list_parametres_application(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[ParametreApplicationDB]:
    # Lecture ouverte à tout utilisateur authentifié (pas de require_permission) : l'appli
    # mobile interne doit pouvoir savoir si le mode hors-ligne est activé quel que soit le
    # rôle connecté (vendeur, caissier...), avant même d'utiliser la caisse.
    return sorted(db.query(ParametreApplicationDB).all(), key=lambda p: p.ordre)


@router.put("/application/{parametre_id}", response_model=ParametreApplication)
def modifier_parametre_application(
    parametre_id: str,
    payload: ParametreApplicationUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ParametreApplicationDB:
    require_permission(db, current_user, SECURITE_GESTION)
    p = db.get(ParametreApplicationDB, parametre_id)
    if not p:
        raise HTTPException(status_code=404, detail="Paramètre introuvable")
    p.actif = payload.actif
    p.updated_by = f"{current_user.prenom} {current_user.nom}"
    log_audit(
        db, f"Paramètre application { 'activé' if payload.actif else 'désactivé' } — {p.label}",
        f"{current_user.prenom} {current_user.nom}",
    )
    db.commit()
    db.refresh(p)
    return p


@router.get("/fiscal", response_model=ParametreFiscal)
def get_parametre_fiscal_route(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ParametreFiscalDB:
    # Lecture ouverte à tout utilisateur authentifié — les documents commerciaux (facture, reçu,
    # bons de commande/réception) doivent pouvoir vérifier la ventilation TVA quel que soit le rôle.
    return get_parametre_fiscal(db)


@router.put("/fiscal", response_model=ParametreFiscal)
def modifier_parametre_fiscal(
    payload: ParametreFiscalUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ParametreFiscalDB:
    require_permission(db, current_user, SECURITE_GESTION)
    p = get_parametre_fiscal(db)
    p.taux = payload.taux
    p.actif = payload.actif
    p.updated_by = f"{current_user.prenom} {current_user.nom}"
    log_audit(
        db, f"Paramètre TVA modifié — taux {int(payload.taux * 100)} %, { 'appliquée' if payload.actif else 'désactivée' }",
        f"{current_user.prenom} {current_user.nom}",
    )
    db.commit()
    db.refresh(p)
    return p


def _to_bareme_schema(b: BaremeCreditBeneficiaireDB, etablissements_by_id: dict[str, EtablissementDB]) -> BaremeCreditBeneficiaire:
    return BaremeCreditBeneficiaire(
        id=b.id, etablissement_id=b.etablissement_id,
        etablissement_nom=etablissements_by_id[b.etablissement_id].nom if b.etablissement_id in etablissements_by_id else None,
        poste=b.poste, plafond=b.plafond, date_debut=b.date_debut, date_fin=b.date_fin,
    )


@router.get("/bareme-credit-beneficiaires", response_model=list[BaremeCreditBeneficiaire])
def list_bareme_credit_beneficiaires(
    etablissement_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[BaremeCreditBeneficiaire]:
    # Lecture ouverte — la fiche bénéficiaire a besoin de résoudre le plafond sans nécessairement
    # gérer le barème.
    query = db.query(BaremeCreditBeneficiaireDB)
    if etablissement_id:
        query = query.filter(BaremeCreditBeneficiaireDB.etablissement_id == etablissement_id)
    etablissements_by_id = {e.id: e for e in db.query(EtablissementDB).all()}
    return [_to_bareme_schema(b, etablissements_by_id) for b in query.all()]


@router.post("/bareme-credit-beneficiaires", response_model=BaremeCreditBeneficiaire, status_code=201)
def create_bareme_credit_beneficiaire(
    payload: BaremeCreditBeneficiaireCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> BaremeCreditBeneficiaire:
    require_permission(db, current_user, BAREME_CREDIT_BENEFICIAIRE_GESTION)
    if payload.etablissement_id and not db.get(EtablissementDB, payload.etablissement_id):
        raise HTTPException(status_code=404, detail="Établissement introuvable")
    conflit = verifier_chevauchement_bareme(db, payload.etablissement_id, payload.poste, payload.date_debut, payload.date_fin)
    if conflit:
        raise HTTPException(status_code=409, detail="Une période existante pour ce poste (et cet établissement) chevauche déjà cet intervalle")
    auteur = f"{current_user.prenom} {current_user.nom}"
    b = BaremeCreditBeneficiaireDB(id=str(uuid.uuid4())[:8], created_by=auteur, updated_by=auteur, **payload.model_dump())
    db.add(b)
    db.commit()
    db.refresh(b)
    etablissements_by_id = {e.id: e for e in db.query(EtablissementDB).all()}
    return _to_bareme_schema(b, etablissements_by_id)


@router.delete("/bareme-credit-beneficiaires/{bareme_id}", status_code=204)
def delete_bareme_credit_beneficiaire(
    bareme_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, BAREME_CREDIT_BENEFICIAIRE_GESTION)
    b = db.get(BaremeCreditBeneficiaireDB, bareme_id)
    if not b:
        raise HTTPException(status_code=404, detail="Barème introuvable")
    db.delete(b)
    db.commit()


def _managed_categories(db: Session) -> list[str]:
    rows = db.query(ReferentielDB.categorie).distinct().all()
    categories = {r[0] for r in rows}
    categories.update(REFERENTIELS.keys())
    return sorted(categories)


@router.get("/referentiels", response_model=dict[str, list[ReferentielItem]])
def list_referentiels(db: Session = Depends(get_db)) -> dict[str, list[ReferentielItem]]:
    result: dict[str, list[ReferentielItem]] = {}
    for categorie in _managed_categories(db):
        rows = db.query(ReferentielDB).filter(ReferentielDB.categorie == categorie).all()
        result[categorie] = [ReferentielItem(id=r.id, nom=r.nom) for r in rows]
    return result


@router.get("/referentiels/{categorie}", response_model=list[ReferentielItem])
def get_referentiel(categorie: str, db: Session = Depends(get_db)) -> list[ReferentielItem]:
    rows = db.query(ReferentielDB).filter(ReferentielDB.categorie == categorie).all()
    return [ReferentielItem(id=r.id, nom=r.nom) for r in rows]


@router.post("/referentiels/{categorie}", response_model=ReferentielItem, status_code=201)
def create_referentiel_item(
    categorie: str,
    payload: ReferentielCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ReferentielItem:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    auteur = f"{current_user.prenom} {current_user.nom}"
    item = ReferentielDB(id=str(uuid.uuid4())[:8], categorie=categorie, nom=payload.nom, created_by=auteur, updated_by=auteur)
    db.add(item)
    db.commit()
    db.refresh(item)
    return ReferentielItem(id=item.id, nom=item.nom)


@router.put("/referentiels/{categorie}/{item_id}", response_model=ReferentielItem)
def update_referentiel_item(
    categorie: str,
    item_id: str,
    payload: ReferentielUpdate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ReferentielItem:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    item = db.query(ReferentielDB).filter(ReferentielDB.id == item_id, ReferentielDB.categorie == categorie).first()
    if not item:
        raise HTTPException(status_code=404, detail="Référentiel introuvable")
    item.nom = payload.nom
    item.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(item)
    return ReferentielItem(id=item.id, nom=item.nom)


@router.delete("/referentiels/{categorie}/{item_id}", status_code=204)
def delete_referentiel_item(
    categorie: str,
    item_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> None:
    require_permission(db, current_user, REFERENTIELS_GESTION)
    item = db.query(ReferentielDB).filter(ReferentielDB.id == item_id, ReferentielDB.categorie == categorie).first()
    if not item:
        raise HTTPException(status_code=404, detail="Référentiel introuvable")
    db.delete(item)
    db.commit()
