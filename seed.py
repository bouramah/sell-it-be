"""Seed the database with realistic starting data matching the KFSTORE design.

Run once against an empty `kfstore` database (after `alembic upgrade head`):
    source .venv/bin/activate && python seed.py

Default password for every seeded user: "kfstore2026" (change on first login).
"""

from app.core.database import Base, SessionLocal, engine
from app.core.security import DEFAULT_PASSWORD, hash_password
from app.data.fixtures import (
    BOUTIQUES,
    CAISSES,
    CLIENTS,
    COMMANDES_CLIENTS,
    COMMANDES_FOURNISSEURS,
    DETTES,
    ECARTS_INVENTAIRE,
    FOURNISSEURS,
    MOUVEMENTS_CAISSE,
    MOUVEMENTS_STOCK,
    PRODUITS,
    REFERENTIELS,
    REMBOURSEMENTS,
    STOCKS,
    TRANSFERTS,
    UTILISATEURS,
)
from app.db_models.models import (
    BoutiqueDB,
    BoutiqueSecteurDB,
    CaisseDB,
    ClientDB,
    CommandeClientDB,
    CommandeFournisseurDB,
    DetteDB,
    EcartInventaireDB,
    FournisseurDB,
    MouvementCaisseDB,
    MouvementStockDB,
    ProduitDB,
    ReferentielDB,
    RemboursementDB,
    StockBoutiqueDB,
    TransfertStockDB,
    UtilisateurDB,
)


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(BoutiqueDB).count() == 0:
            for b in BOUTIQUES:
                row = BoutiqueDB(
                    id=b.id, nom=b.nom, quartier=b.quartier, commune=b.commune, ville=b.ville,
                    horaires=b.horaires, responsable=b.responsable, statut=b.statut, telephone=b.telephone,
                )
                row.secteurs = [BoutiqueSecteurDB(boutique_id=b.id, secteur=s) for s in b.secteurs]
                db.add(row)
            print(f"Boutiques : {len(BOUTIQUES)} insérées")
        else:
            print("Boutiques déjà présentes, ignoré")

        if db.query(ProduitDB).count() == 0:
            for p in PRODUITS:
                db.add(ProduitDB(
                    id=p.id, nom=p.nom, secteur=p.secteur, categorie=p.categorie, prix=p.prix,
                    unite=p.unite, code_barres=p.code_barres, date_peremption=p.date_peremption,
                ))
            print(f"Produits : {len(PRODUITS)} insérés")
        else:
            print("Produits déjà présents, ignoré")

        if db.query(FournisseurDB).count() == 0:
            for f in FOURNISSEURS:
                db.add(FournisseurDB(id=f.id, nom=f.nom, secteur=f.secteur, conditions_paiement=f.conditions_paiement, contact=f.contact))
            print(f"Fournisseurs : {len(FOURNISSEURS)} insérés")
        else:
            print("Fournisseurs déjà présents, ignoré")

        db.commit()

        if db.query(UtilisateurDB).count() == 0:
            boutiques_by_id = {b.id: b for b in db.query(BoutiqueDB).all()}
            for u in UTILISATEURS:
                db.add(UtilisateurDB(
                    id=u.id, nom=u.nom, prenom=u.prenom, contact=u.contact,
                    mot_de_passe_hash=hash_password(DEFAULT_PASSWORD), role=u.role, statut=u.statut,
                    derniere_connexion=u.derniere_connexion,
                    boutiques=[boutiques_by_id[bid] for bid in u.boutique_ids if bid in boutiques_by_id],
                ))
            db.commit()
            print(f"Utilisateurs : {len(UTILISATEURS)} insérés (mot de passe par défaut : {DEFAULT_PASSWORD!r})")
        else:
            print("Utilisateurs déjà présents, ignoré")

        if db.query(ClientDB).count() == 0:
            for c in CLIENTS:
                db.add(ClientDB(id=c.id, nom=c.nom, contact=c.contact, boutique_id=c.boutique_id, segment=c.segment, credit_autorise=c.credit_autorise))
            print(f"Clients : {len(CLIENTS)} insérés")
        else:
            print("Clients déjà présents, ignoré")

        if db.query(StockBoutiqueDB).count() == 0:
            for s in STOCKS:
                db.add(StockBoutiqueDB(
                    boutique_id=s.boutique_id, produit_id=s.produit_id, quantite_disponible=s.quantite_disponible,
                    quantite_reservee=s.quantite_reservee, seuil_alerte=s.seuil_alerte, derniere_mouvement=s.derniere_mouvement,
                ))
            print(f"Stock : {len(STOCKS)} lignes insérées")
        else:
            print("Stock déjà présent, ignoré")

        if db.query(MouvementStockDB).count() == 0:
            for m in MOUVEMENTS_STOCK:
                db.add(MouvementStockDB(
                    id=m.id, horodatage=m.horodatage, produit_id=m.produit_id, boutique_id=m.boutique_id,
                    motif=m.motif, operateur=m.operateur, quantite=m.quantite,
                ))
            print(f"Mouvements de stock : {len(MOUVEMENTS_STOCK)} insérés")
        else:
            print("Mouvements de stock déjà présents, ignoré")

        if db.query(EcartInventaireDB).count() == 0:
            for e in ECARTS_INVENTAIRE:
                db.add(EcartInventaireDB(id=e.id, produit_id=e.produit_id, boutique_id=e.boutique_id, theorique=e.theorique, reel=e.reel, statut=e.statut))
            print(f"Écarts d'inventaire : {len(ECARTS_INVENTAIRE)} insérés")
        else:
            print("Écarts d'inventaire déjà présents, ignoré")

        if db.query(CaisseDB).count() == 0:
            for c in CAISSES:
                db.add(CaisseDB(
                    id=c.id, boutique_id=c.boutique_id, libelle=c.libelle, statut=c.statut,
                    fond_initial=c.fond_initial, solde_theorique=c.solde_theorique, solde_reel=c.solde_reel, operateur=c.operateur,
                ))
            print(f"Caisses : {len(CAISSES)} insérées")
        else:
            print("Caisses déjà présentes, ignoré")

        db.commit()

        if db.query(MouvementCaisseDB).count() == 0:
            for m in MOUVEMENTS_CAISSE:
                db.add(MouvementCaisseDB(
                    id=m.id, horodatage=m.horodatage, boutique_id=m.boutique_id, caisse_id=next(
                        c.id for c in CAISSES if c.boutique_id == m.boutique_id and c.libelle == m.caisse_libelle
                    ), caisse_libelle=m.caisse_libelle, type=m.type, motif=m.motif, operateur=m.operateur, montant=m.montant,
                ))
            print(f"Mouvements de caisse : {len(MOUVEMENTS_CAISSE)} insérés")
        else:
            print("Mouvements de caisse déjà présents, ignoré")

        if db.query(CommandeClientDB).count() == 0:
            for c in COMMANDES_CLIENTS:
                db.add(CommandeClientDB(id=c.id, client_nom=c.client_nom, boutique_id=c.boutique_id, canal=c.canal, mode_paiement=c.mode_paiement, montant=c.montant, statut=c.statut))
            print(f"Commandes clients : {len(COMMANDES_CLIENTS)} insérées")
        else:
            print("Commandes clients déjà présentes, ignoré")

        if db.query(CommandeFournisseurDB).count() == 0:
            for c in COMMANDES_FOURNISSEURS:
                db.add(CommandeFournisseurDB(id=c.id, fournisseur_id=c.fournisseur_id, boutique_id=c.boutique_id, date_attendue=c.date_attendue, montant=c.montant, statut=c.statut))
            print(f"Commandes fournisseurs : {len(COMMANDES_FOURNISSEURS)} insérées")
        else:
            print("Commandes fournisseurs déjà présentes, ignoré")

        if db.query(DetteDB).count() == 0:
            for d in DETTES:
                db.add(DetteDB(
                    id=d.id, tiers_type=d.tiers_type, tiers_nom=d.tiers_nom, boutique_id=d.boutique_id,
                    montant_initial=d.montant_initial, solde_restant=d.solde_restant, echeance=d.echeance, statut=d.statut,
                ))
            print(f"Dettes/créances : {len(DETTES)} insérées")
        else:
            print("Dettes/créances déjà présentes, ignoré")

        db.commit()

        if db.query(RemboursementDB).count() == 0:
            for r in REMBOURSEMENTS:
                db.add(RemboursementDB(id=r.id, dette_id=r.dette_id, montant=r.montant, mode_paiement=r.mode_paiement, date=r.date, operateur=r.operateur))
            print(f"Remboursements : {len(REMBOURSEMENTS)} insérés")
        else:
            print("Remboursements déjà présents, ignoré")

        if db.query(TransfertStockDB).count() == 0:
            for t in TRANSFERTS:
                db.add(TransfertStockDB(
                    id=t.id, produit_id=t.produit_id, boutique_source_id=t.boutique_source_id,
                    boutique_destination_id=t.boutique_destination_id, quantite=t.quantite, demandeur=t.demandeur, statut=t.statut,
                ))
            print(f"Transferts de stock : {len(TRANSFERTS)} insérés")
        else:
            print("Transferts de stock déjà présents, ignoré")

        if db.query(ReferentielDB).count() == 0:
            count = 0
            for categorie, items in REFERENTIELS.items():
                if categorie == "secteurs":
                    continue  # fixed enum, not a managed référentiel
                for item in items:
                    db.add(ReferentielDB(id=item.id, categorie=categorie, nom=item.nom))
                    count += 1
            print(f"Référentiels : {count} insérés")
        else:
            print("Référentiels déjà présents, ignoré")

        db.commit()

    finally:
        db.close()


if __name__ == "__main__":
    seed()
