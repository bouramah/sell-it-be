"""TVA — les prix enregistrés dans KFSTORE sont TTC (prix affiché = prix payé,
cf. décision produit) ; ce module ne recalcule donc jamais un prix, il se contente
d'en extraire la ventilation HT / TVA pour l'affichage sur les documents
commerciaux (facture, reçu, bons de commande/réception)."""

TAUX_TVA = 0.18


def ventilation_tva(montant_ttc: float) -> tuple[float, float]:
    """Renvoie (montant_ht, montant_tva) à partir d'un montant TTC."""
    montant_ht = montant_ttc / (1 + TAUX_TVA)
    return montant_ht, montant_ttc - montant_ht
