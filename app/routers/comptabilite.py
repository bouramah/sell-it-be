from pydantic import BaseModel

from fastapi import APIRouter
from app.data.fixtures import COMPTES_RESULTAT
from app.models.schemas import CompteResultatBoutique

router = APIRouter(prefix="/api/v1/comptabilite", tags=["comptabilite"])


class ComptabiliteConsolidee(BaseModel):
    ca_consolide: float
    marge_nette_consolidee: float
    depenses_consolidees: float
    marge_nette_moyenne_pct: float
    comptes: list[CompteResultatBoutique]


@router.get("", response_model=ComptabiliteConsolidee)
def get_comptabilite() -> ComptabiliteConsolidee:
    ca = sum(c.chiffre_affaires for c in COMPTES_RESULTAT)
    marge = sum(c.marge_nette for c in COMPTES_RESULTAT)
    depenses = sum(c.depenses for c in COMPTES_RESULTAT)
    return ComptabiliteConsolidee(
        ca_consolide=ca,
        marge_nette_consolidee=marge,
        depenses_consolidees=depenses,
        marge_nette_moyenne_pct=round((marge / ca) * 100, 1) if ca else 0,
        comptes=COMPTES_RESULTAT,
    )
