from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Table, Column, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.schemas import (
    CanalCommande,
    DroitAcces,
    MotifMouvementStock,
    ModePaiement,
    OriginePromotion,
    PalierPrix,
    SegmentClient,
    StatutBoutique,
    StatutCaisse,
    StatutCommandeClient,
    StatutCommandeFournisseur,
    StatutDemandeCredit,
    StatutDette,
    StatutEcartInventaire,
    StatutLivraison,
    StatutPaiement,
    StatutPromotion,
    StatutTransfert,
    StatutValidationDepense,
    StatutValidationRemise,
    TiersType,
    TypeMouvementCaisse,
)

utilisateur_boutiques = Table(
    "utilisateur_boutiques",
    Base.metadata,
    Column("utilisateur_id", String(40), ForeignKey("utilisateurs.id", ondelete="CASCADE"), primary_key=True),
    Column("boutique_id", String(40), ForeignKey("boutiques.id", ondelete="CASCADE"), primary_key=True),
)

client_boutiques = Table(
    "client_boutiques",
    Base.metadata,
    Column("client_id", String(40), ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
    Column("boutique_id", String(40), ForeignKey("boutiques.id", ondelete="CASCADE"), primary_key=True),
)


class AuditMixin:
    """created_at/updated_at : gérés par la DB (server_default/onupdate), aucune plomberie
    applicative nécessaire. created_by/updated_by : nullable, à peupler explicitement dans les
    routers avec current_user là où c'est pertinent — jamais confiance dans une valeur fournie
    par le client. Exclu de BoutiqueSecteurDB (table de jonction pure sans identité propre),
    PrixPeriodeDB/PrixAchatDB (portent déjà cree_le/modifie_par, équivalents dédiés) et
    JournalAuditDB (déjà horodatage/auteur, journal immuable — updated_* n'a pas de sens là)."""
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(160), nullable=True)


class BoutiqueDB(AuditMixin, Base):
    __tablename__ = "boutiques"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(120))
    quartier: Mapped[str] = mapped_column(String(120))
    commune: Mapped[str] = mapped_column(String(120))
    ville: Mapped[str] = mapped_column(String(120))
    horaires: Mapped[str] = mapped_column(String(120))
    responsable: Mapped[str] = mapped_column(String(120))
    statut: Mapped[StatutBoutique] = mapped_column(Enum(StatutBoutique))
    telephone: Mapped[str] = mapped_column(String(40))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    secteur_geo_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("secteurs_geo.id", ondelete="SET NULL"), nullable=True)

    secteurs: Mapped[list["BoutiqueSecteurDB"]] = relationship(
        back_populates="boutique", cascade="all, delete-orphan"
    )
    utilisateurs: Mapped[list["UtilisateurDB"]] = relationship(
        secondary=utilisateur_boutiques, back_populates="boutiques"
    )
    clients: Mapped[list["ClientDB"]] = relationship(
        secondary=client_boutiques, back_populates="boutiques"
    )


class BoutiqueSecteurDB(Base):
    __tablename__ = "boutique_secteurs"

    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id", ondelete="CASCADE"), primary_key=True)
    secteur: Mapped[str] = mapped_column(String(60), primary_key=True)

    boutique: Mapped["BoutiqueDB"] = relationship(back_populates="secteurs")


class RoleDB(AuditMixin, Base):
    """Rôles applicatifs, en base plutôt qu'en code — cf. CDC §3.3 : "id, libellé, liste des
    droits (matrice), portée (boutique / multi-boutique / global siège)". La portée n'a que
    deux valeurs utiles ici : "boutique" (limité aux boutiques de rattachement de
    l'utilisateur, une ou plusieurs) et "reseau" (l'ensemble du réseau, cf. critère
    d'acceptation #2)."""
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    libelle: Mapped[str] = mapped_column(String(120))
    portee: Mapped[str] = mapped_column(String(20))
    ordre: Mapped[int] = mapped_column(Integer, default=0)
    systeme: Mapped[bool] = mapped_column(Boolean, default=False)


class UtilisateurDB(AuditMixin, Base):
    __tablename__ = "utilisateurs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(120))
    prenom: Mapped[str] = mapped_column(String(120))
    contact: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(60), ForeignKey("roles.id"))
    statut: Mapped[str] = mapped_column(String(20), default="actif")
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    push_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    secteur_geo_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("secteurs_geo.id", ondelete="SET NULL"), nullable=True)
    # Verrouillage après tentatives échouées (CDC §7.1) — piloté par le paramètre de
    # sécurité "verrouillage_tentatives" (voir ParametreSecuriteDB).
    tentatives_echouees: Mapped[int] = mapped_column(Integer, default=0)
    verrouille_jusqua: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Expiration de session par inactivité (CDC §7.1) — piloté par le paramètre de
    # sécurité "expiration_session" ; mis à jour à chaque requête authentifiée.
    derniere_activite: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    role_ref: Mapped["RoleDB"] = relationship(foreign_keys=[role], lazy="joined")
    boutiques: Mapped[list["BoutiqueDB"]] = relationship(
        secondary=utilisateur_boutiques, back_populates="utilisateurs"
    )


class ProduitDB(AuditMixin, Base):
    __tablename__ = "produits"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(160))
    secteur: Mapped[str] = mapped_column(String(60))
    categorie: Mapped[str] = mapped_column(String(120))
    # Quantité à partir de laquelle le palier est suggéré par défaut à la vente (reste modifiable).
    seuil_semi_gros: Mapped[int] = mapped_column(Integer, default=10)
    seuil_gros: Mapped[int] = mapped_column(Integer, default=50)
    unite: Mapped[str] = mapped_column(String(40))
    code_barres: Mapped[str] = mapped_column(String(40), unique=True)
    date_peremption: Mapped[date | None] = mapped_column(Date, nullable=True)

    images: Mapped[list["ProduitImageDB"]] = relationship(
        back_populates="produit", cascade="all, delete-orphan", order_by="ProduitImageDB.position"
    )


class ProduitImageDB(AuditMixin, Base):
    __tablename__ = "produit_images"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(Integer, default=0)

    produit: Mapped["ProduitDB"] = relationship(back_populates="images")


class PrixPeriodeDB(Base):
    """Prix d'un produit valable sur une période [date_debut, date_fin] — date_fin NULL = période
    encore ouverte. boutique_id NULL = prix de référence réseau, sinon surcharge de cette boutique
    (qui prévaut sur le réseau pour les dates qu'elle couvre). Aucune période ne peut chevaucher une
    autre pour le même (produit_id, boutique_id, palier) — contrôlé en application, cf.
    app/services/pricing.py::verifier_chevauchement. C'est la seule source de vérité pour le prix :
    le « prix actuel » est simplement la période active à la date du jour."""
    __tablename__ = "prix_periodes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id", ondelete="CASCADE"))
    boutique_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("boutiques.id", ondelete="CASCADE"), nullable=True)
    palier: Mapped[PalierPrix] = mapped_column(Enum(PalierPrix))
    prix: Mapped[float] = mapped_column(Float)
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    modifie_par: Mapped[str] = mapped_column(String(160))
    cree_le: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PrixAchatDB(Base):
    """Prix d'achat d'un produit auprès d'un fournisseur donné, sur une période de validité —
    même principe que PrixPeriodeDB côté vente (palier = palier de quantité négociée avec ce
    fournisseur, pas de portée réseau : un prix d'achat est toujours propre à un fournisseur)."""
    __tablename__ = "prix_achats"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id", ondelete="CASCADE"))
    fournisseur_id: Mapped[str] = mapped_column(String(40), ForeignKey("fournisseurs.id", ondelete="CASCADE"))
    palier: Mapped[PalierPrix] = mapped_column(Enum(PalierPrix))
    prix: Mapped[float] = mapped_column(Float)
    date_debut: Mapped[date] = mapped_column(Date)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    modifie_par: Mapped[str] = mapped_column(String(160))
    cree_le: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReferentielDB(AuditMixin, Base):
    """Managed lookup lists (secteurs, villes, communes, quartiers, canaux de vente, ...)."""

    __tablename__ = "referentiels"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    categorie: Mapped[str] = mapped_column(String(60), index=True)
    nom: Mapped[str] = mapped_column(String(160))


class FournisseurDB(AuditMixin, Base):
    __tablename__ = "fournisseurs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(160))
    secteur: Mapped[str] = mapped_column(String(60))
    conditions_paiement: Mapped[str] = mapped_column(String(200))
    contact: Mapped[str] = mapped_column(String(60))
    secteur_geo_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("secteurs_geo.id", ondelete="SET NULL"), nullable=True)


# --- Découpage administratif (Région > Ville > Commune > Quartier > Secteur) ----------------
# Sert à localiser précisément les clients (facilite les tournées de livraison, et servira à
# l'appli mobile client) — cf. décision produit du 2026-08-14. "SecteurGeoDB" est nommé ainsi
# pour ne pas entrer en collision avec le "secteur" métier existant (habillement, alimentation
# générale…) porté par ProduitDB/BoutiqueDB ; côté utilisateur, ce niveau reste affiché "Secteur".
# Les champs quartier/commune/ville en texte libre sur ClientDB (ci-dessous) restent en place
# pour compatibilité — secteur_geo_id est la référence structurée à privilégier désormais.


class RegionDB(AuditMixin, Base):
    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(120), unique=True)


class VilleDB(AuditMixin, Base):
    __tablename__ = "villes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(120))
    region_id: Mapped[str] = mapped_column(String(40), ForeignKey("regions.id", ondelete="CASCADE"))


class CommuneDB(AuditMixin, Base):
    __tablename__ = "communes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(120))
    ville_id: Mapped[str] = mapped_column(String(40), ForeignKey("villes.id", ondelete="CASCADE"))


class QuartierGeoDB(AuditMixin, Base):
    __tablename__ = "quartiers_geo"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(120))
    commune_id: Mapped[str] = mapped_column(String(40), ForeignKey("communes.id", ondelete="CASCADE"))


class SecteurGeoDB(AuditMixin, Base):
    __tablename__ = "secteurs_geo"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(120))
    quartier_id: Mapped[str] = mapped_column(String(40), ForeignKey("quartiers_geo.id", ondelete="CASCADE"))


class ClientDB(AuditMixin, Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(160))
    # unique : sert désormais aussi d'identifiant de connexion à l'appli mobile client (§6.1 —
    # authentification par numéro de téléphone + code à usage unique).
    contact: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    segment: Mapped[SegmentClient] = mapped_column(Enum(SegmentClient))
    credit_autorise: Mapped[bool] = mapped_column(Boolean, default=False)
    quartier: Mapped[str | None] = mapped_column(String(120), nullable=True)
    commune: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ville: Mapped[str | None] = mapped_column(String(120), nullable=True)
    secteur_geo_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("secteurs_geo.id", ondelete="SET NULL"), nullable=True)

    boutiques: Mapped[list["BoutiqueDB"]] = relationship(
        secondary=client_boutiques, back_populates="clients"
    )


class StockBoutiqueDB(AuditMixin, Base):
    __tablename__ = "stock_boutiques"

    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id", ondelete="CASCADE"), primary_key=True)
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id", ondelete="CASCADE"), primary_key=True)
    quantite_disponible: Mapped[int] = mapped_column(Integer, default=0)
    quantite_reservee: Mapped[int] = mapped_column(Integer, default=0)
    seuil_alerte: Mapped[int] = mapped_column(Integer, default=0)
    derniere_mouvement: Mapped[datetime] = mapped_column(DateTime)


class MouvementStockDB(AuditMixin, Base):
    __tablename__ = "mouvements_stock"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime)
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id"))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    motif: Mapped[MotifMouvementStock] = mapped_column(Enum(MotifMouvementStock))
    operateur: Mapped[str] = mapped_column(String(120))
    quantite: Mapped[int] = mapped_column(Integer)
    stock_avant: Mapped[int] = mapped_column(Integer, default=0)
    stock_apres: Mapped[int] = mapped_column(Integer, default=0)


class EcartInventaireDB(AuditMixin, Base):
    __tablename__ = "ecarts_inventaire"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id"))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    theorique: Mapped[int] = mapped_column(Integer)
    reel: Mapped[int] = mapped_column(Integer)
    statut: Mapped[StatutEcartInventaire] = mapped_column(Enum(StatutEcartInventaire))


class CaisseDB(AuditMixin, Base):
    __tablename__ = "caisses"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    libelle: Mapped[str] = mapped_column(String(80))
    statut: Mapped[StatutCaisse] = mapped_column(Enum(StatutCaisse))
    fond_initial: Mapped[float] = mapped_column(Float)
    solde_theorique: Mapped[float] = mapped_column(Float)
    solde_reel: Mapped[float] = mapped_column(Float)
    operateur: Mapped[str] = mapped_column(String(120))


class MouvementCaisseDB(AuditMixin, Base):
    __tablename__ = "mouvements_caisse"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime)
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    caisse_id: Mapped[str] = mapped_column(String(40), ForeignKey("caisses.id"))
    caisse_libelle: Mapped[str] = mapped_column(String(80))
    type: Mapped[TypeMouvementCaisse] = mapped_column(Enum(TypeMouvementCaisse))
    motif: Mapped[str] = mapped_column(String(160))
    operateur: Mapped[str] = mapped_column(String(120))
    montant: Mapped[float] = mapped_column(Float)
    solde_avant: Mapped[float] = mapped_column(Float, default=0)
    solde_apres: Mapped[float] = mapped_column(Float, default=0)


class CommandeClientDB(AuditMixin, Base):
    __tablename__ = "commandes_clients"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    client_nom: Mapped[str] = mapped_column(String(160))
    # Lien fiable vers le client authentifié qui a passé cette commande (appli mobile client) —
    # nullable : une vente directe en boutique ("client de passage") n'a pas forcément
    # d'identité client formelle. client_nom reste la source d'affichage/historique.
    client_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    canal: Mapped[CanalCommande] = mapped_column(Enum(CanalCommande))
    mode_paiement: Mapped[ModePaiement] = mapped_column(Enum(ModePaiement))
    montant: Mapped[float] = mapped_column(Float)
    statut: Mapped[StatutCommandeClient] = mapped_column(Enum(StatutCommandeClient))
    date_creation: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    remise_motif: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remise_statut: Mapped[StatutValidationRemise] = mapped_column(Enum(StatutValidationRemise), default=StatutValidationRemise.aucune)
    remise_validee_par: Mapped[str | None] = mapped_column(String(120), nullable=True)
    remise_validee_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    lignes: Mapped[list["LigneCommandeClientDB"]] = relationship(back_populates="commande", cascade="all, delete-orphan")


class LigneCommandeClientDB(AuditMixin, Base):
    __tablename__ = "lignes_commandes_clients"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    commande_id: Mapped[str] = mapped_column(String(40), ForeignKey("commandes_clients.id", ondelete="CASCADE"))
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id"))
    quantite: Mapped[int] = mapped_column(Integer)
    # Palier utilisé pour cette ligne — nécessaire pour reconstituer le prix catalogue de référence
    # à la date de la vente (cf. prix_effectif_a_date), le prix dépendant du palier.
    palier: Mapped[PalierPrix] = mapped_column(Enum(PalierPrix), default=PalierPrix.detail)
    prix_unitaire: Mapped[float] = mapped_column(Float)

    commande: Mapped["CommandeClientDB"] = relationship(back_populates="lignes")


class CommandeFournisseurDB(AuditMixin, Base):
    __tablename__ = "commandes_fournisseurs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    fournisseur_id: Mapped[str] = mapped_column(String(40), ForeignKey("fournisseurs.id"))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    date_attendue: Mapped[date] = mapped_column(Date)
    montant: Mapped[float] = mapped_column(Float)
    statut: Mapped[StatutCommandeFournisseur] = mapped_column(Enum(StatutCommandeFournisseur))
    date_reception: Mapped[date | None] = mapped_column(Date, nullable=True)

    lignes: Mapped[list["LigneCommandeFournisseurDB"]] = relationship(back_populates="commande", cascade="all, delete-orphan")


class LigneCommandeFournisseurDB(AuditMixin, Base):
    __tablename__ = "lignes_commandes_fournisseurs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    commande_id: Mapped[str] = mapped_column(String(40), ForeignKey("commandes_fournisseurs.id", ondelete="CASCADE"))
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id"))
    quantite: Mapped[int] = mapped_column(Integer)
    prix_unitaire: Mapped[float] = mapped_column(Float)
    quantite_recue: Mapped[int] = mapped_column(Integer, default=0)

    commande: Mapped["CommandeFournisseurDB"] = relationship(back_populates="lignes")


class DetteDB(AuditMixin, Base):
    __tablename__ = "dettes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tiers_type: Mapped[TiersType] = mapped_column(Enum(TiersType))
    tiers_nom: Mapped[str] = mapped_column(String(160))
    # Lien fiable vers le client authentifié (créance client uniquement — une dette fournisseur
    # n'a pas de client_id) — nullable pour les mêmes raisons que CommandeClientDB.client_id.
    client_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    montant_initial: Mapped[float] = mapped_column(Float)
    solde_restant: Mapped[float] = mapped_column(Float)
    echeance: Mapped[date] = mapped_column(Date)
    statut: Mapped[StatutDette] = mapped_column(Enum(StatutDette))

    remboursements: Mapped[list["RemboursementDB"]] = relationship(back_populates="dette", cascade="all, delete-orphan")


class RemboursementDB(AuditMixin, Base):
    __tablename__ = "remboursements"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    dette_id: Mapped[str] = mapped_column(String(40), ForeignKey("dettes.id", ondelete="CASCADE"))
    caisse_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("caisses.id"), nullable=True)
    montant: Mapped[float] = mapped_column(Float)
    mode_paiement: Mapped[ModePaiement] = mapped_column(Enum(ModePaiement))
    date: Mapped[date] = mapped_column(Date)
    operateur: Mapped[str] = mapped_column(String(120))

    dette: Mapped["DetteDB"] = relationship(back_populates="remboursements")


class DemandeCreditDB(AuditMixin, Base):
    """Demande de crédit initiée par un client depuis l'appli mobile — jamais de dette créée
    automatiquement : une validation côté boutique (staff) est requise (cf. mon_credit.py /
    dettes.py), conformément au CDC §3.1 : "Aucune opération de crédit n'est activée sans
    validation d'un utilisateur habilité de la boutique"."""
    __tablename__ = "demandes_credit"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(40), ForeignKey("clients.id", ondelete="CASCADE"))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    montant_souhaite: Mapped[float] = mapped_column(Float)
    motif: Mapped[str] = mapped_column(String(255))
    statut: Mapped[StatutDemandeCredit] = mapped_column(Enum(StatutDemandeCredit), default=StatutDemandeCredit.en_attente)
    date_creation: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TransfertStockDB(AuditMixin, Base):
    """En-tête d'un transfert — peut porter plusieurs produits (une seule opération, CDC),
    chacun sur sa propre ligne (même pattern que CommandeClientDB/lignes_commandes_clients)."""
    __tablename__ = "transferts_stock"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    boutique_source_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    boutique_destination_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    demandeur: Mapped[str] = mapped_column(String(160))
    statut: Mapped[StatutTransfert] = mapped_column(Enum(StatutTransfert))

    lignes: Mapped[list["LigneTransfertStockDB"]] = relationship(back_populates="transfert", cascade="all, delete-orphan")


class LigneTransfertStockDB(AuditMixin, Base):
    __tablename__ = "lignes_transferts_stock"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    transfert_id: Mapped[str] = mapped_column(String(40), ForeignKey("transferts_stock.id", ondelete="CASCADE"))
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id"))
    quantite: Mapped[int] = mapped_column(Integer)
    # Écart à la réception (casse/perte en transit, cf. CDC 3.9) : quantite_recue < quantite
    # signifie qu'une partie ne s'est pas rendue à destination — motif_ecart devient alors
    # obligatoire (contrôlé côté routeur, jamais confiance dans une valeur envoyée sans motif).
    quantite_recue: Mapped[int | None] = mapped_column(Integer, nullable=True)
    motif_ecart: Mapped[str | None] = mapped_column(String(255), nullable=True)

    transfert: Mapped["TransfertStockDB"] = relationship(back_populates="lignes")


class LivraisonDB(AuditMixin, Base):
    __tablename__ = "livraisons"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    commande_id: Mapped[str] = mapped_column(String(40), ForeignKey("commandes_clients.id"))
    livreur: Mapped[str] = mapped_column(String(160))
    livreur_user_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("utilisateurs.id"), nullable=True)
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    adresse: Mapped[str] = mapped_column(String(255))
    creneau: Mapped[str] = mapped_column(String(80))
    statut: Mapped[StatutLivraison] = mapped_column(Enum(StatutLivraison))
    preuve_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class DepenseDB(AuditMixin, Base):
    __tablename__ = "depenses"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    caisse_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("caisses.id"), nullable=True)
    categorie: Mapped[str] = mapped_column(String(120))
    auteur: Mapped[str] = mapped_column(String(160))
    date: Mapped[date] = mapped_column(Date)
    montant: Mapped[float] = mapped_column(Float)
    statut_validation: Mapped[StatutValidationDepense] = mapped_column(Enum(StatutValidationDepense))
    justificatif_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PaiementClientDB(AuditMixin, Base):
    __tablename__ = "paiements_clients"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    client_nom: Mapped[str] = mapped_column(String(160))
    reference: Mapped[str] = mapped_column(String(160))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    caisse_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("caisses.id"), nullable=True)
    mode_paiement: Mapped[ModePaiement] = mapped_column(Enum(ModePaiement))
    date: Mapped[date] = mapped_column(Date)
    montant: Mapped[float] = mapped_column(Float)
    statut: Mapped[StatutPaiement] = mapped_column(Enum(StatutPaiement))


class PaiementFournisseurDB(AuditMixin, Base):
    __tablename__ = "paiements_fournisseurs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    fournisseur_nom: Mapped[str] = mapped_column(String(160))
    reference: Mapped[str] = mapped_column(String(160))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    caisse_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("caisses.id"), nullable=True)
    mode_paiement: Mapped[ModePaiement] = mapped_column(Enum(ModePaiement))
    date: Mapped[date] = mapped_column(Date)
    montant: Mapped[float] = mapped_column(Float)
    statut: Mapped[StatutPaiement] = mapped_column(Enum(StatutPaiement))
    document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PermissionDB(AuditMixin, Base):
    __tablename__ = "permissions"

    module_action: Mapped[str] = mapped_column(String(160), primary_key=True)
    role: Mapped[str] = mapped_column(String(60), ForeignKey("roles.id"), primary_key=True)
    droit: Mapped[DroitAcces] = mapped_column(Enum(DroitAcces))
    ordre: Mapped[int] = mapped_column(Integer, default=0)


class PromotionDB(AuditMixin, Base):
    __tablename__ = "promotions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(160))
    boutique_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("boutiques.id"), nullable=True)
    secteur: Mapped[str | None] = mapped_column(String(60), nullable=True)
    origine: Mapped[OriginePromotion] = mapped_column(Enum(OriginePromotion))
    impact_estime: Mapped[str] = mapped_column(String(255))
    statut: Mapped[StatutPromotion] = mapped_column(Enum(StatutPromotion))


class JournalAuditDB(Base):
    __tablename__ = "journal_audit"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime)
    action: Mapped[str] = mapped_column(String(255))
    auteur: Mapped[str] = mapped_column(String(160))
    # SET NULL (pas CASCADE) : le journal est immuable et doit survivre à la suppression de la boutique référencée.
    boutique_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("boutiques.id", ondelete="SET NULL"), nullable=True)
    # Valeur avant/après en JSON texte (CDC §7.3) — nullable : de nombreuses actions
    # journalisées (connexion, envoi de code...) n'ont pas de valeur métier à comparer.
    valeur_avant: Mapped[str | None] = mapped_column(Text, nullable=True)
    valeur_apres: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Identité structurée en plus du texte libre `auteur` (qui reste la valeur affichée telle
    # quelle, même après un renommage) — permet de filtrer fiablement "tout ce qu'a fait X" sans
    # dépendre d'un nom en texte libre. SET NULL : le journal survit à la suppression du compte.
    utilisateur_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True, index=True)
    client_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    # "web" | "mobile_interne" | "mobile_client" | "inconnu" — déclaré par chaque appli via
    # l'en-tête X-Client-Canal ; distingue back-office et mobile comme demandé (au-delà du
    # simple staff/client déjà porté par le claim JWT "typ").
    canal: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    methode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    chemin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    statut_code: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MessageAssistantDB(Base):
    """Historique des conversations avec l'assistant IA (appli mobile client) — journal
    immuable comme JournalAuditDB, jamais modifié après écriture. Permet de retrouver la
    conversation en rouvrant l'écran (sinon perdue à chaque démontage de AssistantScreen)."""
    __tablename__ = "messages_assistant"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(40), ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    auteur: Mapped[str] = mapped_column(String(10))  # "client" | "bot"
    texte: Mapped[str] = mapped_column(Text)
    horodatage: Mapped[datetime] = mapped_column(DateTime)


class ParametreSecuriteDB(AuditMixin, Base):
    __tablename__ = "parametres_securite"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(Boolean, default=False)
    ordre: Mapped[int] = mapped_column(Integer, default=0)


class ParametreApplicationDB(AuditMixin, Base):
    """Interrupteurs fonctionnels globaux (distincts des paramètres de sécurité §7) — lecture
    ouverte à tout utilisateur authentifié (l'appli mobile interne doit pouvoir savoir si le
    mode hors-ligne est activé avant même d'être un compte admin), écriture réservée à
    l'administrateur via SECURITE_GESTION."""
    __tablename__ = "parametres_application"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    label: Mapped[str] = mapped_column(String(200))
    actif: Mapped[bool] = mapped_column(Boolean, default=False)
    ordre: Mapped[int] = mapped_column(Integer, default=0)


class ParametreFiscalDB(AuditMixin, Base):
    """Ligne unique (id='tva') — taux et application de la TVA configurables plutôt que codés
    en dur (app/services/fiscalite.py), pour permettre de désactiver la ventilation HT/TVA sur
    les documents commerciaux sans toucher au code."""
    __tablename__ = "parametres_fiscaux"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    taux: Mapped[float] = mapped_column(Float, default=0.18)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)


class OtpCodeDB(AuditMixin, Base):
    """Code à usage unique envoyé par SMS — réinitialisation de mot de passe ou
    2FA à la connexion (CDC §7.1), distingués par `objectif` pour qu'un code
    généré pour l'un ne puisse jamais être rejoué pour l'autre."""
    __tablename__ = "otp_codes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    contact: Mapped[str] = mapped_column(String(30))
    code_hash: Mapped[str] = mapped_column(String(255))
    objectif: Mapped[str] = mapped_column(String(20), default="reinitialisation")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
