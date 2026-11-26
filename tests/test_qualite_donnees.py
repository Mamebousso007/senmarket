"""Tests de qualité sur les partitions PRODUITES (data/processed et data/rejected).

- Lancés par le pipeline sur la partition qu'il vient de produire (variable SENMARKET_PARTITION) ;
- lancés à la main (python -m pytest), ils contrôlent toutes les partitions nettoyées ;
- ignorés (pas en échec) s'il n'existe encore aucune partition nettoyée.
"""

import os

import pandas as pd
import pytest

from senmarket.chemins import dossier_processed, dossier_rejected, lister_partitions
from senmarket.generateur import COLONNES
from senmarket.nettoyage import CLES, CLES_ETRANGERES

ENTIERS = {
    "produits": ["prix_catalogue_xof"],
    "lignes_commande": ["quantite", "prix_unitaire_xof", "montant_xof"],
    "paiements": ["montant_xof"],
    "avis": ["note"],
}


def partitions_a_controler():
    choisie = os.getenv("SENMARKET_PARTITION")
    return [choisie] if choisie else lister_partitions("processed")


PARTITIONS = partitions_a_controler()
sans_partition = pytest.mark.skipif(not PARTITIONS, reason="aucune partition nettoyée : lance le pipeline")


def lire(run_date):
    dossier = dossier_processed(run_date)
    return {nom: pd.read_parquet(dossier / f"{nom}.parquet") for nom in COLONNES}


def problemes_d_integrite(tables, run_date):
    """Liste lisible des problèmes d'une partition (liste vide = partition saine)."""
    problemes = []
    for nom, df in tables.items():
        if list(df.columns) != COLONNES[nom]:
            problemes.append(f"{nom} : colonnes {list(df.columns)} au lieu de {COLONNES[nom]}")
            continue
        if not df[CLES[nom]].is_unique or df[CLES[nom]].isna().any():
            problemes.append(f"{nom} : clé primaire {CLES[nom]} vide ou en double")
        for col in ENTIERS.get(nom, []):
            if df[col].dtype != "int64":
                problemes.append(f"{nom}.{col} : type {df[col].dtype} au lieu de int64")
        for col in [c for c in df.columns if c.startswith("date_")]:
            if (df[col] >= pd.Timestamp(run_date) + pd.Timedelta(days=1)).any():
                problemes.append(f"{nom}.{col} : date postérieure à {run_date}")
    lc = tables["lignes_commande"]
    if "quantite" in lc and (lc["montant_xof"] != lc["quantite"] * lc["prix_unitaire_xof"]).any():
        problemes.append("lignes_commande : montant_xof différent de quantite × prix_unitaire_xof")
    for enfant, colonne, parent, facultatif in CLES_ETRANGERES:
        valeurs = tables[enfant][colonne]
        if facultatif:
            valeurs = valeurs.dropna()
        orphelines = int((~valeurs.isin(tables[parent][CLES[parent]])).sum())
        if orphelines:
            problemes.append(f"{enfant}.{colonne} → {parent} : {orphelines} clé(s) orpheline(s)")
    return problemes


# --- Les contrôles, partition par partition -------------------------------------

@sans_partition
@pytest.mark.parametrize("run_date", PARTITIONS)
def test_integrite_de_la_partition(run_date):
    assert problemes_d_integrite(lire(run_date), run_date) == []


@sans_partition
@pytest.mark.parametrize("run_date", PARTITIONS)
def test_chaque_rejet_a_un_motif(run_date):
    for nom in COLONNES:
        rejets = pd.read_csv(dossier_rejected(run_date) / f"{nom}_rejetes.csv", dtype=str)
        assert rejets["raison_rejet"].notna().all(), nom


@sans_partition
@pytest.mark.parametrize("run_date", PARTITIONS)
def test_bilan_coherent_avec_les_fichiers(run_date):
    bilan = pd.read_csv(dossier_rejected(run_date) / "bilan_nettoyage.csv").set_index("table")
    for nom in COLONNES:
        acceptes = len(pd.read_parquet(dossier_processed(run_date) / f"{nom}.parquet"))
        rejetes = len(pd.read_csv(dossier_rejected(run_date) / f"{nom}_rejetes.csv", dtype=str))
        assert bilan.loc[nom, "accepte"] == acceptes, nom
        assert bilan.loc[nom, "rejete"] == rejetes, nom
        assert bilan.loc[nom, "brut"] == acceptes + rejetes, nom


# --- Test d'erreur : les contrôles détectent bien une partition abîmée -----------

def test_les_controles_detectent_les_problemes():
    tables = {nom: pd.DataFrame(columns=cols) for nom, cols in COLONNES.items()}   # tables vides
    tables["clients"] = pd.DataFrame([["CLI0000001"] + ["x"] * 5 + [pd.Timestamp("2026-01-01")]],
                                     columns=COLONNES["clients"])
    tables["commandes"] = pd.DataFrame(
        [["CMD0000001", "CLI0000001", pd.Timestamp("2026-01-01"), "livree"],
         ["CMD0000001", "CLI9999999", pd.Timestamp("2027-06-15"), "livree"]],   # doublon, orphelin, futur
        columns=COLONNES["commandes"])
    problemes = " | ".join(problemes_d_integrite(tables, "2026-10-29"))
    assert "commandes : clé primaire commande_id vide ou en double" in problemes
    assert "commandes.client_id → clients : 1 clé(s) orpheline(s)" in problemes
    assert "commandes.date_commande : date postérieure à 2026-10-29" in problemes
