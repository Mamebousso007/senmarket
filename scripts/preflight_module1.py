"""Contrôle de pré-vol du Module 1 : mes données sont-elles prêtes ? (partie A4)

Lance-le depuis la racine du projet :  python scripts/preflight_module1.py
Puis garde sa sortie dans docs/MESURES.md.
"""

import sys

import pandas as pd

from senmarket.chemins import dossier_processed, lister_partitions

CLES = {
    "clients": "client_id", "vendeurs": "vendeur_id", "produits": "produit_id",
    "commandes": "commande_id", "lignes_commande": "ligne_commande_id",
    "paiements": "paiement_id", "avis": "avis_id", "navigation": "evenement_id",
}
# (table enfant, colonne, table parente)
RELATIONS = [
    ("commandes", "client_id", "clients"),
    ("lignes_commande", "commande_id", "commandes"),
    ("lignes_commande", "produit_id", "produits"),
    ("paiements", "commande_id", "commandes"),
    ("avis", "produit_id", "produits"),
]

# Partition à contrôler : celle donnée en argument, sinon la plus récente
partitions = lister_partitions("processed")
if not partitions:
    raise SystemExit("Aucune partition nettoyée : lance le pipeline du module 0 avant.")
run_date = sys.argv[1] if len(sys.argv) > 1 else partitions[-1]
dossier = dossier_processed(run_date)
print("Partition contrôlée :", dossier.name)

tables = {nom: pd.read_parquet(dossier / f"{nom}.parquet") for nom in CLES}
for nom, df in tables.items():
    print(f"{nom:<16}{len(df):>9} lignes | clé primaire unique : {df[CLES[nom]].is_unique}")

for enfant, colonne, parent in RELATIONS:
    orphelins = ~tables[enfant][colonne].isin(tables[parent][CLES[parent]])
    print(f"{enfant}.{colonne} -> {parent} : {orphelins.sum()} orphelin(s)")

# Le paiement est-il égal à la somme des lignes de sa commande ?
lignes = tables["lignes_commande"].groupby("commande_id")["montant_xof"].sum()
paye = tables["paiements"].groupby("commande_id")["montant_xof"].sum()
comparaison = pd.concat([lignes, paye], axis=1, keys=["lignes", "paye"]).dropna()
print(f"Paiement égal à la somme des lignes : {(comparaison.lignes == comparaison.paye).mean():.1%}")

# Les colonnes que le chapitre 1 va ajouter existent-elles déjà ?
for table, colonne in [("produits", "stock"), ("avis", "commentaire"), ("paiements", "reference_transaction")]:
    print(f"{table}.{colonne} présent : {colonne in tables[table].columns}")
