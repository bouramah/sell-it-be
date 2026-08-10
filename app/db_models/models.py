from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Table, Column, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.schemas import (
    CanalCommande,
    MotifMouvementStock,
    ModePaiement,
    Role,
    Secteur,
    SegmentClient,
    StatutBoutique,
    StatutCaisse,
    StatutCommandeClient,
    StatutCommandeFournisseur,
    StatutDette,
    StatutEcartInventaire,
    StatutLivraison,
    StatutPaiement,
    StatutTransfert,
    StatutValidationDepense,
    TiersType,
    TypeMouvementCaisse,
)

utilisateur_boutiques = Table(
    "utilisateur_boutiques",
    Base.metadata,
    Column("utilisateur_id", String(40), ForeignKey("utilisateurs.id", ondelete="CASCADE"), primary_key=True),
    Column("boutique_id", String(40), ForeignKey("boutiques.id", ondelete="CASCADE"), primary_key=True),
)


class BoutiqueDB(Base):
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

    secteurs: Mapped[list["BoutiqueSecteurDB"]] = relationship(
        back_populates="boutique", cascade="all, delete-orphan"
    )
    utilisateurs: Mapped[list["UtilisateurDB"]] = relationship(
        secondary=utilisateur_boutiques, back_populates="boutiques"
    )


class BoutiqueSecteurDB(Base):
    __tablename__ = "boutique_secteurs"

    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id", ondelete="CASCADE"), primary_key=True)
    secteur: Mapped[Secteur] = mapped_column(Enum(Secteur), primary_key=True)

    boutique: Mapped["BoutiqueDB"] = relationship(back_populates="secteurs")


class UtilisateurDB(Base):
    __tablename__ = "utilisateurs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(120))
    prenom: Mapped[str] = mapped_column(String(120))
    contact: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role))
    statut: Mapped[str] = mapped_column(String(20), default="actif")
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    boutiques: Mapped[list["BoutiqueDB"]] = relationship(
        secondary=utilisateur_boutiques, back_populates="utilisateurs"
    )


class ProduitDB(Base):
    __tablename__ = "produits"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(160))
    secteur: Mapped[Secteur] = mapped_column(Enum(Secteur))
    categorie: Mapped[str] = mapped_column(String(120))
    prix: Mapped[float] = mapped_column(Float)
    unite: Mapped[str] = mapped_column(String(40))
    code_barres: Mapped[str] = mapped_column(String(40), unique=True)
    date_peremption: Mapped[date | None] = mapped_column(Date, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ReferentielDB(Base):
    """Managed lookup lists (villes, communes, quartiers, canaux de vente, ...).

    Secteurs is intentionally NOT stored here: it's a fixed enum baked into
    Boutique/Produit elsewhere in the schema, not a free-form référentiel.
    """

    __tablename__ = "referentiels"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    categorie: Mapped[str] = mapped_column(String(60), index=True)
    nom: Mapped[str] = mapped_column(String(160))


class FournisseurDB(Base):
    __tablename__ = "fournisseurs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(160))
    secteur: Mapped[Secteur] = mapped_column(Enum(Secteur))
    conditions_paiement: Mapped[str] = mapped_column(String(200))
    contact: Mapped[str] = mapped_column(String(60))


class ClientDB(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    nom: Mapped[str] = mapped_column(String(160))
    contact: Mapped[str] = mapped_column(String(60))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    segment: Mapped[SegmentClient] = mapped_column(Enum(SegmentClient))
    credit_autorise: Mapped[bool] = mapped_column(Boolean, default=False)


class StockBoutiqueDB(Base):
    __tablename__ = "stock_boutiques"

    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id", ondelete="CASCADE"), primary_key=True)
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id", ondelete="CASCADE"), primary_key=True)
    quantite_disponible: Mapped[int] = mapped_column(Integer, default=0)
    quantite_reservee: Mapped[int] = mapped_column(Integer, default=0)
    seuil_alerte: Mapped[int] = mapped_column(Integer, default=0)
    derniere_mouvement: Mapped[datetime] = mapped_column(DateTime)


class MouvementStockDB(Base):
    __tablename__ = "mouvements_stock"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime)
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id"))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    motif: Mapped[MotifMouvementStock] = mapped_column(Enum(MotifMouvementStock))
    operateur: Mapped[str] = mapped_column(String(120))
    quantite: Mapped[int] = mapped_column(Integer)


class EcartInventaireDB(Base):
    __tablename__ = "ecarts_inventaire"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id"))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    theorique: Mapped[int] = mapped_column(Integer)
    reel: Mapped[int] = mapped_column(Integer)
    statut: Mapped[StatutEcartInventaire] = mapped_column(Enum(StatutEcartInventaire))


class CaisseDB(Base):
    __tablename__ = "caisses"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    libelle: Mapped[str] = mapped_column(String(80))
    statut: Mapped[StatutCaisse] = mapped_column(Enum(StatutCaisse))
    fond_initial: Mapped[float] = mapped_column(Float)
    solde_theorique: Mapped[float] = mapped_column(Float)
    solde_reel: Mapped[float] = mapped_column(Float)
    operateur: Mapped[str] = mapped_column(String(120))


class MouvementCaisseDB(Base):
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


class CommandeClientDB(Base):
    __tablename__ = "commandes_clients"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    client_nom: Mapped[str] = mapped_column(String(160))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    canal: Mapped[CanalCommande] = mapped_column(Enum(CanalCommande))
    mode_paiement: Mapped[ModePaiement] = mapped_column(Enum(ModePaiement))
    montant: Mapped[float] = mapped_column(Float)
    statut: Mapped[StatutCommandeClient] = mapped_column(Enum(StatutCommandeClient))
    date_creation: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    lignes: Mapped[list["LigneCommandeClientDB"]] = relationship(back_populates="commande", cascade="all, delete-orphan")


class LigneCommandeClientDB(Base):
    __tablename__ = "lignes_commandes_clients"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    commande_id: Mapped[str] = mapped_column(String(40), ForeignKey("commandes_clients.id", ondelete="CASCADE"))
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id"))
    quantite: Mapped[int] = mapped_column(Integer)
    prix_unitaire: Mapped[float] = mapped_column(Float)

    commande: Mapped["CommandeClientDB"] = relationship(back_populates="lignes")


class CommandeFournisseurDB(Base):
    __tablename__ = "commandes_fournisseurs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    fournisseur_id: Mapped[str] = mapped_column(String(40), ForeignKey("fournisseurs.id"))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    date_attendue: Mapped[date] = mapped_column(Date)
    montant: Mapped[float] = mapped_column(Float)
    statut: Mapped[StatutCommandeFournisseur] = mapped_column(Enum(StatutCommandeFournisseur))
    date_reception: Mapped[date | None] = mapped_column(Date, nullable=True)

    lignes: Mapped[list["LigneCommandeFournisseurDB"]] = relationship(back_populates="commande", cascade="all, delete-orphan")


class LigneCommandeFournisseurDB(Base):
    __tablename__ = "lignes_commandes_fournisseurs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    commande_id: Mapped[str] = mapped_column(String(40), ForeignKey("commandes_fournisseurs.id", ondelete="CASCADE"))
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id"))
    quantite: Mapped[int] = mapped_column(Integer)
    prix_unitaire: Mapped[float] = mapped_column(Float)
    quantite_recue: Mapped[int] = mapped_column(Integer, default=0)

    commande: Mapped["CommandeFournisseurDB"] = relationship(back_populates="lignes")


class DetteDB(Base):
    __tablename__ = "dettes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tiers_type: Mapped[TiersType] = mapped_column(Enum(TiersType))
    tiers_nom: Mapped[str] = mapped_column(String(160))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    montant_initial: Mapped[float] = mapped_column(Float)
    solde_restant: Mapped[float] = mapped_column(Float)
    echeance: Mapped[date] = mapped_column(Date)
    statut: Mapped[StatutDette] = mapped_column(Enum(StatutDette))

    remboursements: Mapped[list["RemboursementDB"]] = relationship(back_populates="dette", cascade="all, delete-orphan")


class RemboursementDB(Base):
    __tablename__ = "remboursements"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    dette_id: Mapped[str] = mapped_column(String(40), ForeignKey("dettes.id", ondelete="CASCADE"))
    montant: Mapped[float] = mapped_column(Float)
    mode_paiement: Mapped[ModePaiement] = mapped_column(Enum(ModePaiement))
    date: Mapped[date] = mapped_column(Date)
    operateur: Mapped[str] = mapped_column(String(120))

    dette: Mapped["DetteDB"] = relationship(back_populates="remboursements")


class TransfertStockDB(Base):
    __tablename__ = "transferts_stock"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    produit_id: Mapped[str] = mapped_column(String(40), ForeignKey("produits.id"))
    boutique_source_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    boutique_destination_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    quantite: Mapped[int] = mapped_column(Integer)
    demandeur: Mapped[str] = mapped_column(String(160))
    statut: Mapped[StatutTransfert] = mapped_column(Enum(StatutTransfert))


class LivraisonDB(Base):
    __tablename__ = "livraisons"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    commande_id: Mapped[str] = mapped_column(String(40), ForeignKey("commandes_clients.id"))
    livreur: Mapped[str] = mapped_column(String(160))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    adresse: Mapped[str] = mapped_column(String(255))
    creneau: Mapped[str] = mapped_column(String(80))
    statut: Mapped[StatutLivraison] = mapped_column(Enum(StatutLivraison))
    preuve_disponible: Mapped[bool] = mapped_column(Boolean, default=False)


class DepenseDB(Base):
    __tablename__ = "depenses"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    categorie: Mapped[str] = mapped_column(String(120))
    auteur: Mapped[str] = mapped_column(String(160))
    date: Mapped[date] = mapped_column(Date)
    montant: Mapped[float] = mapped_column(Float)
    statut_validation: Mapped[StatutValidationDepense] = mapped_column(Enum(StatutValidationDepense))
    justificatif_disponible: Mapped[bool] = mapped_column(Boolean, default=False)


class PaiementClientDB(Base):
    __tablename__ = "paiements_clients"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    client_nom: Mapped[str] = mapped_column(String(160))
    reference: Mapped[str] = mapped_column(String(160))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    mode_paiement: Mapped[ModePaiement] = mapped_column(Enum(ModePaiement))
    date: Mapped[date] = mapped_column(Date)
    montant: Mapped[float] = mapped_column(Float)
    statut: Mapped[StatutPaiement] = mapped_column(Enum(StatutPaiement))


class PaiementFournisseurDB(Base):
    __tablename__ = "paiements_fournisseurs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    fournisseur_nom: Mapped[str] = mapped_column(String(160))
    reference: Mapped[str] = mapped_column(String(160))
    boutique_id: Mapped[str] = mapped_column(String(40), ForeignKey("boutiques.id"))
    mode_paiement: Mapped[ModePaiement] = mapped_column(Enum(ModePaiement))
    date: Mapped[date] = mapped_column(Date)
    montant: Mapped[float] = mapped_column(Float)
    statut: Mapped[StatutPaiement] = mapped_column(Enum(StatutPaiement))
