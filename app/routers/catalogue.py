"""Catalogue public — CDC §3.5 : "Catalogue en ligne consultable par les clients, filtrable
par boutique, quartier/ville, secteur et catégorie de produit — accessible depuis l'application
mobile client et depuis le site web." Aucune authentification requise (décision produit du
2026-08-15 : vitrine ouverte, la connexion n'intervient qu'au moment de commander) — donc
aucune donnée sensible exposée ici (jamais de prix d'achat, de quantité réservée brute, ni de
données internes)."""
from collections import defaultdict
from datetime import date

from pydantic import BaseModel
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException
from app.core.database import get_db
from app.db_models.models import BoutiqueDB, ProduitDB, StockBoutiqueDB
from app.models.schemas import PalierPrix, StatutBoutique
from app.services.pricing import prix_effectifs_batch, resoudre_prix

router = APIRouter(prefix="/api/v1/catalogue", tags=["catalogue"])


class BoutiquePublique(BaseModel):
    id: str
    nom: str
    secteurs: list[str]
    quartier: str
    commune: str
    ville: str
    horaires: str
    telephone: str
    latitude: float | None = None
    longitude: float | None = None


class ProduitCatalogue(BaseModel):
    id: str
    nom: str
    secteur: str
    categorie: str
    unite: str
    images: list[str]
    prix_detail: float
    prix_semi_gros: float
    prix_gros: float
    # Vendable réellement (quantité disponible − déjà réservée par d'autres commandes en
    # cours), jamais la quantité brute de stock — évite d'afficher un article "en stock"
    # alors qu'il est déjà entièrement réservé par ailleurs.
    disponible: int
    boutiques_disponibles: list[str]


@router.get("/boutiques", response_model=list[BoutiquePublique])
def list_boutiques_publiques(
    ville: str | None = None,
    commune: str | None = None,
    secteur: str | None = None,
    db: Session = Depends(get_db),
) -> list[BoutiquePublique]:
    query = db.query(BoutiqueDB).filter(BoutiqueDB.statut == StatutBoutique.active)
    if ville:
        query = query.filter(BoutiqueDB.ville == ville)
    if commune:
        query = query.filter(BoutiqueDB.commune == commune)
    boutiques = query.all()
    resultat = [
        BoutiquePublique(
            id=b.id, nom=b.nom, secteurs=[s.secteur for s in b.secteurs], quartier=b.quartier,
            commune=b.commune, ville=b.ville, horaires=b.horaires, telephone=b.telephone,
            latitude=b.latitude, longitude=b.longitude,
        )
        for b in boutiques
    ]
    if secteur:
        resultat = [b for b in resultat if secteur in b.secteurs]
    return resultat


@router.get("/produits", response_model=list[ProduitCatalogue])
def catalogue_produits(
    boutique_id: str | None = None,
    secteur: str | None = None,
    categorie: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
) -> list[ProduitCatalogue]:
    boutiques_actives_ids = {b.id for b in db.query(BoutiqueDB).filter(BoutiqueDB.statut == StatutBoutique.active).all()}
    if boutique_id and boutique_id not in boutiques_actives_ids:
        raise HTTPException(status_code=404, detail="Boutique introuvable ou fermée")

    query = db.query(ProduitDB)
    if secteur:
        query = query.filter(ProduitDB.secteur == secteur)
    if categorie:
        query = query.filter(ProduitDB.categorie == categorie)
    if q:
        query = query.filter(ProduitDB.nom.ilike(f"%{q}%"))
    produits = query.all()
    if not produits:
        return []

    stock_query = db.query(StockBoutiqueDB).filter(StockBoutiqueDB.boutique_id.in_(boutiques_actives_ids))
    stock_query = stock_query.filter(StockBoutiqueDB.boutique_id == boutique_id) if boutique_id else stock_query
    stock_by_produit: dict[str, list[StockBoutiqueDB]] = defaultdict(list)
    for s in stock_query.all():
        stock_by_produit[s.produit_id].append(s)

    produit_ids = {p.id for p in produits}
    cache = prix_effectifs_batch(db, {boutique_id} if boutique_id else set(), produit_ids, date.today())

    resultat = []
    for p in produits:
        lignes = stock_by_produit.get(p.id, [])
        disponible = sum(max(0, l.quantite_disponible - l.quantite_reservee) for l in lignes)
        boutiques_disponibles = [l.boutique_id for l in lignes if l.quantite_disponible - l.quantite_reservee > 0]
        if boutique_id and disponible == 0:
            continue
        resultat.append(ProduitCatalogue(
            id=p.id, nom=p.nom, secteur=p.secteur, categorie=p.categorie, unite=p.unite,
            images=[img.url for img in sorted(p.images, key=lambda i: i.position)],
            prix_detail=resoudre_prix(cache, boutique_id or "", p.id, PalierPrix.detail) or 0.0,
            prix_semi_gros=resoudre_prix(cache, boutique_id or "", p.id, PalierPrix.semi_gros) or 0.0,
            prix_gros=resoudre_prix(cache, boutique_id or "", p.id, PalierPrix.gros) or 0.0,
            disponible=disponible,
            boutiques_disponibles=boutiques_disponibles,
        ))
    return resultat
