"""Seed the database with realistic starting data matching the KFSTORE design.

Run once against an empty `kfstore` database (after `alembic upgrade head`):
    source .venv/bin/activate && python seed.py

Default password for every seeded user: "kfstore2026" (change on first login).
"""

from app.core.database import Base, SessionLocal, engine
from app.core.security import DEFAULT_PASSWORD, hash_password
from app.data.fixtures import BOUTIQUES, PRODUITS, REFERENTIELS, UTILISATEURS
from app.db_models.models import BoutiqueDB, BoutiqueSecteurDB, ProduitDB, ReferentielDB, UtilisateurDB


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(BoutiqueDB).count() == 0:
            for b in BOUTIQUES:
                row = BoutiqueDB(
                    id=b.id,
                    nom=b.nom,
                    quartier=b.quartier,
                    commune=b.commune,
                    ville=b.ville,
                    horaires=b.horaires,
                    responsable=b.responsable,
                    statut=b.statut,
                    telephone=b.telephone,
                )
                row.secteurs = [BoutiqueSecteurDB(boutique_id=b.id, secteur=s) for s in b.secteurs]
                db.add(row)
            print(f"Boutiques : {len(BOUTIQUES)} insérées")
        else:
            print("Boutiques déjà présentes, ignoré")

        if db.query(ProduitDB).count() == 0:
            for p in PRODUITS:
                db.add(
                    ProduitDB(
                        id=p.id,
                        nom=p.nom,
                        secteur=p.secteur,
                        categorie=p.categorie,
                        prix=p.prix,
                        unite=p.unite,
                        code_barres=p.code_barres,
                        date_peremption=p.date_peremption,
                    )
                )
            print(f"Produits : {len(PRODUITS)} insérés")
        else:
            print("Produits déjà présents, ignoré")

        db.commit()

        if db.query(UtilisateurDB).count() == 0:
            boutiques_by_id = {b.id: b for b in db.query(BoutiqueDB).all()}
            for u in UTILISATEURS:
                row = UtilisateurDB(
                    id=u.id,
                    nom=u.nom,
                    prenom=u.prenom,
                    contact=u.contact,
                    mot_de_passe_hash=hash_password(DEFAULT_PASSWORD),
                    role=u.role,
                    statut=u.statut,
                    derniere_connexion=u.derniere_connexion,
                    boutiques=[boutiques_by_id[bid] for bid in u.boutique_ids if bid in boutiques_by_id],
                )
                db.add(row)
            db.commit()
            print(f"Utilisateurs : {len(UTILISATEURS)} insérés (mot de passe par défaut : {DEFAULT_PASSWORD!r})")
        else:
            print("Utilisateurs déjà présents, ignoré")

        if db.query(ReferentielDB).count() == 0:
            count = 0
            for categorie, items in REFERENTIELS.items():
                if categorie == "secteurs":
                    continue  # fixed enum, not a managed référentiel
                for item in items:
                    db.add(ReferentielDB(id=item.id, categorie=categorie, nom=item.nom))
                    count += 1
            db.commit()
            print(f"Référentiels : {count} insérés")
        else:
            print("Référentiels déjà présents, ignoré")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
