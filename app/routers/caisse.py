import uuid
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.authorization import apply_boutique_filter, assert_boutique_access, require_permission
from app.core.database import get_db
from app.core.module_actions import CAISSE_MOUVEMENT, CAISSE_OUVERTURE
from app.core.security import get_current_user
from app.db_models.models import CaisseDB, MouvementCaisseDB, UtilisateurDB
from app.models.schemas import Caisse, StatutCaisse, TypeMouvementCaisse
from app.models.write_schemas import CaisseCreate, CaisseFermeture, MouvementCaisseCreate
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1/caisse", tags=["caisse"])


class LigneMouvementCaisse(BaseModel):
    id: str
    horodatage: str
    boutique_id: str
    caisse_libelle: str
    type: TypeMouvementCaisse
    motif: str
    operateur: str
    montant: float


@router.get("/caisses", response_model=list[Caisse])
def list_caisses(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[CaisseDB]:
    query = apply_boutique_filter(db.query(CaisseDB), CaisseDB.boutique_id, current_user, boutique_id)
    return query.all()


@router.post("/caisses", response_model=Caisse, status_code=201)
def create_caisse(
    payload: CaisseCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CaisseDB:
    require_permission(db, current_user, CAISSE_OUVERTURE)
    assert_boutique_access(current_user, payload.boutique_id)
    auteur = f"{current_user.prenom} {current_user.nom}"
    c = CaisseDB(
        id=str(uuid.uuid4())[:8],
        boutique_id=payload.boutique_id,
        libelle=payload.libelle,
        statut=StatutCaisse.ouverte,
        fond_initial=payload.fond_initial,
        solde_theorique=payload.fond_initial,
        solde_reel=payload.fond_initial,
        operateur=payload.operateur,
        created_by=auteur,
        updated_by=auteur,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.post("/caisses/{caisse_id}/fermer", response_model=Caisse)
def fermer_caisse(
    caisse_id: str,
    payload: CaisseFermeture,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CaisseDB:
    c = db.get(CaisseDB, caisse_id)
    if not c:
        raise HTTPException(status_code=404, detail="Caisse introuvable")
    require_permission(db, current_user, CAISSE_OUVERTURE)
    assert_boutique_access(current_user, c.boutique_id)
    c.solde_reel = payload.solde_reel
    c.statut = StatutCaisse.fermee if payload.solde_reel == c.solde_theorique else StatutCaisse.ecart_signale
    c.updated_by = f"{current_user.prenom} {current_user.nom}"
    if c.statut == StatutCaisse.ecart_signale:
        ecart = abs(payload.solde_reel - c.solde_theorique)
        log_audit(
            db,
            f"Écart de caisse signalé ({ecart:,.0f} GNF) — {c.libelle}".replace(",", " "),
            f"{current_user.prenom} {current_user.nom}",
            c.boutique_id,
        )
    db.commit()
    db.refresh(c)
    return c


@router.post("/caisses/{caisse_id}/rouvrir", response_model=Caisse)
def rouvrir_caisse(
    caisse_id: str,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> CaisseDB:
    c = db.get(CaisseDB, caisse_id)
    if not c:
        raise HTTPException(status_code=404, detail="Caisse introuvable")
    require_permission(db, current_user, CAISSE_OUVERTURE)
    assert_boutique_access(current_user, c.boutique_id)
    c.statut = StatutCaisse.ouverte
    c.updated_by = f"{current_user.prenom} {current_user.nom}"
    db.commit()
    db.refresh(c)
    return c


@router.get("/mouvements", response_model=list[LigneMouvementCaisse])
def list_mouvements_caisse(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[LigneMouvementCaisse]:
    query = apply_boutique_filter(db.query(MouvementCaisseDB), MouvementCaisseDB.boutique_id, current_user, boutique_id)
    rows = sorted(query.all(), key=lambda m: m.horodatage)
    return [
        LigneMouvementCaisse(
            id=m.id,
            horodatage=m.horodatage.isoformat(),
            boutique_id=m.boutique_id,
            caisse_libelle=m.caisse_libelle,
            type=m.type,
            motif=m.motif,
            operateur=m.operateur,
            montant=m.montant,
        )
        for m in rows
    ]


@router.post("/mouvements", response_model=LigneMouvementCaisse, status_code=201)
def create_mouvement_caisse(
    payload: MouvementCaisseCreate,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> LigneMouvementCaisse:
    caisse = db.get(CaisseDB, payload.caisse_id)
    if not caisse:
        raise HTTPException(status_code=404, detail="Caisse introuvable")
    require_permission(db, current_user, CAISSE_MOUVEMENT)
    assert_boutique_access(current_user, caisse.boutique_id)
    if caisse.statut != StatutCaisse.ouverte:
        raise HTTPException(status_code=400, detail="La caisse doit être ouverte pour enregistrer un mouvement")

    signed_montant = payload.montant if payload.type == TypeMouvementCaisse.encaissement else -payload.montant
    now = datetime.now(timezone.utc)
    auteur = f"{current_user.prenom} {current_user.nom}"
    m = MouvementCaisseDB(
        id=str(uuid.uuid4())[:8],
        horodatage=now,
        boutique_id=caisse.boutique_id,
        caisse_id=caisse.id,
        caisse_libelle=caisse.libelle,
        type=payload.type,
        motif=payload.motif,
        operateur=payload.operateur,
        montant=signed_montant,
        created_by=auteur,
        updated_by=auteur,
    )
    db.add(m)
    caisse.solde_theorique += signed_montant
    caisse.updated_by = auteur
    db.commit()
    return LigneMouvementCaisse(
        id=m.id,
        horodatage=m.horodatage.isoformat(),
        boutique_id=m.boutique_id,
        caisse_libelle=m.caisse_libelle,
        type=m.type,
        motif=m.motif,
        operateur=m.operateur,
        montant=m.montant,
    )
