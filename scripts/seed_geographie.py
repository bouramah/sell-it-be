"""Charge le découpage administratif officiel de la Guinée (app/data/geographie_guinee.json,
produit par scripts/extract_geographie.py) dans les tables villes/communes/quartiers_geo/
secteurs_geo — en remplacement des données de test précédentes.

Les régions elles-mêmes ne sont pas touchées (déjà seedées par la migration
1ffc630300b6, les 8 noms correspondent exactement aux clés du JSON) ; on vide
uniquement tout ce qui est en dessous, la suppression cascade jusqu'aux secteurs
(ON DELETE CASCADE sur toute la chaîne villes→communes→quartiers_geo→secteurs_geo).

Idempotent : peut être relancé sans dupliquer (vide avant de recharger).
Usage : cd backend && source .venv/bin/activate && python scripts/seed_geographie.py
"""
import json
import uuid
from pathlib import Path

from app.core.database import SessionLocal
from app.db_models.models import CommuneDB, QuartierGeoDB, RegionDB, SecteurGeoDB, VilleDB

DATA_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "geographie_guinee.json"


def _id() -> str:
    return uuid.uuid4().hex[:16]


def main() -> None:
    geographie = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        regions_by_nom = {r.nom: r.id for r in db.query(RegionDB).all()}
        manquantes = set(geographie.keys()) - set(regions_by_nom.keys())
        if manquantes:
            raise SystemExit(f"Régions absentes de la table regions, à créer avant de continuer : {manquantes}")

        print("Suppression du découpage géographique existant (villes → ... → secteurs)...")
        n_villes_avant = db.query(VilleDB).count()
        db.query(VilleDB).delete(synchronize_session=False)
        db.commit()
        print(f"  {n_villes_avant} ville(s) supprimée(s) (cascade sur communes/quartiers/secteurs).")

        villes_rows, communes_rows, quartiers_rows, secteurs_rows = [], [], [], []

        for region_nom, villes in geographie.items():
            region_id = regions_by_nom[region_nom]
            for ville_nom, communes in villes.items():
                ville_id = _id()
                villes_rows.append({"id": ville_id, "nom": ville_nom, "region_id": region_id})
                for commune_nom, quartiers in communes.items():
                    commune_id = _id()
                    communes_rows.append({"id": commune_id, "nom": commune_nom, "ville_id": ville_id})
                    for quartier_nom, secteurs in quartiers.items():
                        quartier_id = _id()
                        quartiers_rows.append({"id": quartier_id, "nom": quartier_nom, "commune_id": commune_id})
                        for secteur_nom in secteurs:
                            secteurs_rows.append({"id": _id(), "nom": secteur_nom, "quartier_id": quartier_id})

        print(f"Insertion : {len(villes_rows)} villes, {len(communes_rows)} communes, "
              f"{len(quartiers_rows)} quartiers, {len(secteurs_rows)} secteurs...")
        db.bulk_insert_mappings(VilleDB, villes_rows)
        db.bulk_insert_mappings(CommuneDB, communes_rows)
        db.bulk_insert_mappings(QuartierGeoDB, quartiers_rows)
        db.bulk_insert_mappings(SecteurGeoDB, secteurs_rows)
        db.commit()
        print("Terminé.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
