from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.schemas import Role, Secteur, StatutBoutique

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
