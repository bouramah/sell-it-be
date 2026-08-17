"""IA (chapitre 4 du CDC) — phase 1 MVP (§5) : recherche/recommandation produit et prévision
de la demande, sans dépendance à un fournisseur LLM (approches classiques : recherche floue,
co-achat, moyenne de vente réelle). Le chatbot (§4.4) et le reporting en langage naturel (§4.7)
restent en fixtures pour l'instant — ils nécessitent un fournisseur LLM (§6.2), prévu en phase
suivante une fois le choix/la clé fournis."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends
from app.core.authorization import require_permission
from app.core.database import get_db
from app.core.module_actions import MODULES_IA
from app.core.security import get_current_user
from app.data.fixtures import ANOMALIES_REPORTING, CHATBOT_CONFIG, CHATBOT_CONVERSATION_DEMO, SYNTHESE_REPORTING
from app.db_models.models import CommandeClientDB, LigneCommandeClientDB, ProduitDB, StockBoutiqueDB, UtilisateurDB
from app.models.schemas import AnomalieReporting, ConversationMessage, PalierPrix, StatutCommandeClient
from app.services.pricing import prix_effectifs_batch, resoudre_prix

router = APIRouter(prefix="/api/v1/ia", tags=["ia"])

# --- Recherche & recommandation (§4.2) --------------------------------------------------

# Synonymes locaux courants (marché guinéen) — volontairement un simple dict extensible plutôt
# qu'un référentiel géré en base : à faire évoluer vers une vraie gestion admin si le besoin
# grandit, sans changer la forme de l'API (recherche exacte d'abord, ce dict en complément).
SYNONYMES: dict[str, list[str]] = {
    "riz": ["riz parfumé", "riz brisure"],
    "huile": ["huile de palme", "huile végétale"],
    "tele": ["téléviseur", "tv"],
    "tv": ["téléviseur"],
    "frigo": ["réfrigérateur", "congélateur"],
    "portable": ["téléphone", "chargeur téléphone"],
    "savon": ["savon de marseille"],
}

SEUIL_SIMILARITE = 0.45


class ProduitRecommande(BaseModel):
    id: str
    nom: str
    secteur: str
    categorie: str
    unite: str
    images: list[str]
    prix_detail: float
    disponible: int
    raison: str


def _stock_et_prix(db: Session, produits: list[ProduitDB], boutique_id: str | None) -> tuple[dict[str, int], dict]:
    ids = {p.id for p in produits}
    if not ids:
        return {}, {}
    stock_query = db.query(StockBoutiqueDB).filter(StockBoutiqueDB.produit_id.in_(ids))
    if boutique_id:
        stock_query = stock_query.filter(StockBoutiqueDB.boutique_id == boutique_id)
    dispo: dict[str, int] = defaultdict(int)
    for s in stock_query.all():
        dispo[s.produit_id] += max(0, s.quantite_disponible - s.quantite_reservee)
    cache = prix_effectifs_batch(db, {boutique_id} if boutique_id else set(), ids, date.today())
    return dispo, cache


def _vers_recommande(p: ProduitDB, dispo: dict[str, int], cache: dict, boutique_id: str | None, raison: str) -> ProduitRecommande:
    return ProduitRecommande(
        id=p.id, nom=p.nom, secteur=p.secteur, categorie=p.categorie, unite=p.unite,
        images=[img.url for img in sorted(p.images, key=lambda i: i.position)],
        prix_detail=resoudre_prix(cache, boutique_id or "", p.id, PalierPrix.detail) or 0.0,
        disponible=dispo.get(p.id, 0), raison=raison,
    )


@router.get("/recherche", response_model=list[ProduitRecommande])
def recherche_intelligente(
    q: str,
    boutique_id: str | None = None,
    secteur: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[ProduitRecommande]:
    """Tolérante aux fautes de frappe et aux synonymes locaux (§4.2) : correspondance
    exacte/partielle d'abord (nom ou catégorie), recherche floue en repli si rien ne matche."""
    require_permission(db, current_user, MODULES_IA)
    query = db.query(ProduitDB)
    if secteur:
        query = query.filter(ProduitDB.secteur == secteur)
    produits = query.all()

    q_norm = q.strip().lower()
    termes = {q_norm, *SYNONYMES.get(q_norm, [])}

    exacts = [p for p in produits if any(t in p.nom.lower() or t in p.categorie.lower() for t in termes)]
    if exacts:
        resultats, raison = exacts, "Correspondance"
    else:
        # Comparé au nom seul, pas à la catégorie : une catégorie courte ("telephonie") produit
        # un ratio de similarité trompeusement élevé par simple chevauchement de lettres avec
        # une requête sans rapport ("televizeur" ~ "telephonie") — la correspondance exacte
        # ci-dessus couvre déjà le cas "chercher par catégorie".
        scores = [(p, SequenceMatcher(None, q_norm, p.nom.lower()).ratio()) for p in produits]
        scores.sort(key=lambda t: t[1], reverse=True)
        resultats, raison = [p for p, s in scores if s >= SEUIL_SIMILARITE][:20], "Résultat approché"

    dispo, cache = _stock_et_prix(db, resultats, boutique_id)
    return [_vers_recommande(p, dispo, cache, boutique_id, raison) for p in resultats]


# Logique pure (sans dépendance requête/permission), extraite pour être réutilisée à la fois
# par ces endpoints staff et par les endpoints publics équivalents de app/routers/catalogue.py
# (l'appli mobile-client a besoin des mêmes recommandations mais authentifie ses requêtes avec
# un jeton client, incompatible avec get_current_user/require_permission — cf. security.py).


def logique_similaires(db: Session, produit_id: str, limite: int) -> tuple[list[ProduitDB], dict[str, str]]:
    cible = db.get(ProduitDB, produit_id)
    if not cible:
        return [], {}
    candidats = db.query(ProduitDB).filter(ProduitDB.secteur == cible.secteur, ProduitDB.id != produit_id).all()
    candidats.sort(key=lambda p: (p.categorie != cible.categorie, p.nom))
    candidats = candidats[:limite]
    raisons = {p.id: ("Même catégorie" if p.categorie == cible.categorie else "Même secteur") for p in candidats}
    return candidats, raisons


def logique_complementaires(db: Session, produit_id: str, limite: int, jours: int) -> tuple[list[ProduitDB], dict[str, str]]:
    depuis = datetime.utcnow() - timedelta(days=jours)
    commandes_avec_produit = (
        db.query(LigneCommandeClientDB.commande_id)
        .join(CommandeClientDB, CommandeClientDB.id == LigneCommandeClientDB.commande_id)
        .filter(
            LigneCommandeClientDB.produit_id == produit_id,
            CommandeClientDB.statut != StatutCommandeClient.annulee,
            CommandeClientDB.date_creation >= depuis,
        )
    )
    coachats = (
        db.query(LigneCommandeClientDB.produit_id, func.count().label("n"))
        .filter(LigneCommandeClientDB.commande_id.in_(commandes_avec_produit), LigneCommandeClientDB.produit_id != produit_id)
        .group_by(LigneCommandeClientDB.produit_id)
        .order_by(func.count().desc())
        .limit(limite)
        .all()
    )
    produits_by_id = {p.id: p for p in db.query(ProduitDB).filter(ProduitDB.id.in_([c.produit_id for c in coachats])).all()}
    candidats = [produits_by_id[c.produit_id] for c in coachats if c.produit_id in produits_by_id]
    raisons = {p.id: "Souvent acheté avec" for p in candidats}
    return candidats, raisons


def logique_tendances(
    db: Session, boutique_id: str | None, secteur: str | None, jours: int, limite: int
) -> tuple[list[ProduitDB], dict[str, str]]:
    depuis = datetime.utcnow() - timedelta(days=jours)
    query = (
        db.query(LigneCommandeClientDB.produit_id, func.sum(LigneCommandeClientDB.quantite).label("qte"))
        .join(CommandeClientDB, CommandeClientDB.id == LigneCommandeClientDB.commande_id)
        .filter(CommandeClientDB.statut != StatutCommandeClient.annulee, CommandeClientDB.date_creation >= depuis)
    )
    if boutique_id:
        query = query.filter(CommandeClientDB.boutique_id == boutique_id)
    ventes = query.group_by(LigneCommandeClientDB.produit_id).order_by(func.sum(LigneCommandeClientDB.quantite).desc()).limit(limite * 2).all()

    produits_by_id = {p.id: p for p in db.query(ProduitDB).filter(ProduitDB.id.in_([v.produit_id for v in ventes])).all()}
    if secteur:
        ventes = [v for v in ventes if v.produit_id in produits_by_id and produits_by_id[v.produit_id].secteur == secteur]
    ventes = ventes[:limite]
    candidats = [produits_by_id[v.produit_id] for v in ventes if v.produit_id in produits_by_id]
    raisons = {v.produit_id: f"{int(v.qte)} vendus ({jours} j)" for v in ventes if v.produit_id in produits_by_id}
    return candidats, raisons


@router.get("/produits/{produit_id}/similaires", response_model=list[ProduitRecommande])
def produits_similaires(
    produit_id: str,
    boutique_id: str | None = None,
    limite: int = 6,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[ProduitRecommande]:
    """Mise en avant dynamique (§4.2) : même catégorie d'abord, puis même secteur."""
    require_permission(db, current_user, MODULES_IA)
    candidats, raisons = logique_similaires(db, produit_id, limite)
    dispo, cache = _stock_et_prix(db, candidats, boutique_id)
    return [_vers_recommande(p, dispo, cache, boutique_id, raisons[p.id]) for p in candidats]


@router.get("/produits/{produit_id}/complementaires", response_model=list[ProduitRecommande])
def produits_complementaires(
    produit_id: str,
    boutique_id: str | None = None,
    limite: int = 6,
    jours: int = 90,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[ProduitRecommande]:
    """Panier-type (§4.2) : produits le plus souvent achetés dans la même commande que
    produit_id, sur une fenêtre glissante — pas besoin de LLM, une simple analyse de co-achat."""
    require_permission(db, current_user, MODULES_IA)
    candidats, raisons = logique_complementaires(db, produit_id, limite, jours)
    dispo, cache = _stock_et_prix(db, candidats, boutique_id)
    return [_vers_recommande(p, dispo, cache, boutique_id, raisons[p.id]) for p in candidats]


@router.get("/tendances", response_model=list[ProduitRecommande])
def tendances(
    boutique_id: str | None = None,
    secteur: str | None = None,
    jours: int = 30,
    limite: int = 12,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[ProduitRecommande]:
    """Tendances par boutique/secteur (§4.2) : produits les plus vendus sur une fenêtre glissante."""
    require_permission(db, current_user, MODULES_IA)
    candidats, raisons = logique_tendances(db, boutique_id, secteur, jours, limite)
    dispo, cache = _stock_et_prix(db, candidats, boutique_id)
    return [_vers_recommande(p, dispo, cache, boutique_id, raisons[p.id]) for p in candidats]


# --- Prévision de la demande (§4.3) -----------------------------------------------------

class SuggestionAvecProduit(BaseModel):
    produit_id: str
    produit_nom: str
    boutique_id: str
    stock_actuel: int
    ventes_prevues_14j: int
    quantite_suggeree: int
    # "faible" | "moyenne" | "haute" — reflète la profondeur réelle d'historique disponible,
    # pas juste un score arbitraire : l'IA doit rester une aide à la décision transparente.
    confiance: str


@router.get("/previsions", response_model=list[SuggestionAvecProduit])
def previsions_demande(
    boutique_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[SuggestionAvecProduit]:
    """Vitesse de vente réelle (quantité vendue / jours couverts depuis la première vente)
    projetée sur 14 jours, comparée au stock actuel. Volontairement une moyenne simple plutôt
    qu'un modèle statistique élaboré : avec l'historique encore court de KFSTORE (quelques
    jours au démarrage), un modèle plus complexe ne serait pas plus fiable — la confiance
    grandira naturellement avec l'usage réel, sans changement de code."""
    require_permission(db, current_user, MODULES_IA)

    query = (
        db.query(
            LigneCommandeClientDB.produit_id,
            CommandeClientDB.boutique_id,
            func.sum(LigneCommandeClientDB.quantite).label("total"),
            func.min(CommandeClientDB.date_creation).label("premiere"),
            func.count(func.distinct(func.date(CommandeClientDB.date_creation))).label("jours_avec_vente"),
        )
        .join(CommandeClientDB, CommandeClientDB.id == LigneCommandeClientDB.commande_id)
        .filter(CommandeClientDB.statut != StatutCommandeClient.annulee)
    )
    if boutique_id:
        query = query.filter(CommandeClientDB.boutique_id == boutique_id)
    ventes = query.group_by(LigneCommandeClientDB.produit_id, CommandeClientDB.boutique_id).all()
    if not ventes:
        return []

    produit_ids = {v.produit_id for v in ventes}
    produits_by_id = {p.id: p for p in db.query(ProduitDB).filter(ProduitDB.id.in_(produit_ids)).all()}
    stocks = {(s.boutique_id, s.produit_id): s for s in db.query(StockBoutiqueDB).filter(StockBoutiqueDB.produit_id.in_(produit_ids)).all()}

    maintenant = datetime.utcnow()
    resultats = []
    for v in ventes:
        produit = produits_by_id.get(v.produit_id)
        if not produit:
            continue
        jours_couverts = max(1, (maintenant - v.premiere).days + 1)
        vitesse_jour = v.total / jours_couverts
        ventes_prevues_14j = round(vitesse_jour * 14)
        stock = stocks.get((v.boutique_id, v.produit_id))
        stock_actuel = stock.quantite_disponible if stock else 0
        seuil_alerte = stock.seuil_alerte if stock else 0
        quantite_suggeree = max(0, ventes_prevues_14j + seuil_alerte - stock_actuel)
        if quantite_suggeree <= 0:
            continue
        confiance = "haute" if v.jours_avec_vente >= 14 else "moyenne" if v.jours_avec_vente >= 5 else "faible"
        resultats.append(SuggestionAvecProduit(
            produit_id=v.produit_id, produit_nom=produit.nom, boutique_id=v.boutique_id,
            stock_actuel=stock_actuel, ventes_prevues_14j=ventes_prevues_14j,
            quantite_suggeree=quantite_suggeree, confiance=confiance,
        ))
    resultats.sort(key=lambda r: r.quantite_suggeree, reverse=True)
    return resultats


# --- Reporting intelligent & chatbot (§4.4, §4.7) — nécessitent un fournisseur LLM ------
# Phase suivante une fois le choix de fournisseur (OpenAI, décidé) et la clé API fournis.

class ReportingIntelligent(BaseModel):
    synthese: str
    anomalies: list[AnomalieReporting]


@router.get("/reporting", response_model=ReportingIntelligent)
def reporting_intelligent(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> ReportingIntelligent:
    require_permission(db, current_user, MODULES_IA)
    return ReportingIntelligent(synthese=SYNTHESE_REPORTING, anomalies=ANOMALIES_REPORTING)


@router.get("/chatbot/config")
def chatbot_config(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> dict:
    require_permission(db, current_user, MODULES_IA)
    return CHATBOT_CONFIG


@router.get("/chatbot/conversation-demo", response_model=list[ConversationMessage])
def chatbot_conversation_demo(
    db: Session = Depends(get_db),
    current_user: UtilisateurDB = Depends(get_current_user),
) -> list[ConversationMessage]:
    require_permission(db, current_user, MODULES_IA)
    return CHATBOT_CONVERSATION_DEMO
