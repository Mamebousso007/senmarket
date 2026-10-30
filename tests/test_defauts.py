"""Tests de l'injection des défauts : chaque défaut est présent, compté, et la vérité reste intacte."""

import re

import pandas as pd
import pytest

from senmarket.defauts import DEFAUTS_DE_LIGNE, PRIX_OUTLIER, injecter_defauts, lire_options
from senmarket.generateur import calculer_graine, ecrire_brut, generer_verite, journal_simule, main

RUN_DATE = "2026-10-29"
GRAINE = calculer_graine(RUN_DATE, seed=42)


@pytest.fixture(scope="module")
def verite():
    return generer_verite(RUN_DATE, rows=10_000, seed=42)


@pytest.fixture(scope="module")
def abime(verite):
    actifs, taux = lire_options(["tous"], [])
    return injecter_defauts(verite, actifs, taux, RUN_DATE, GRAINE)


def _injectees(bilan, defaut, colonne=None):
    lignes = bilan[bilan["defaut"] == defaut]
    if colonne:
        lignes = lignes[lignes["colonne"] == colonne]
    return int(lignes["lignes_injectees"].sum())


# --- Options ------------------------------------------------------------------

def test_tous_active_les_defauts_de_ligne_seulement():
    actifs, _ = lire_options(["tous"], [])
    assert actifs == DEFAUTS_DE_LIGNE
    assert "encodage_latin1" not in actifs


def test_taux_personnalise():
    _, taux = lire_options(["outlier"], ["outlier=0.05"])
    assert taux["outlier"] == 0.05


@pytest.mark.parametrize("defauts, taux, message", [
    (["inconnu"], [], "Défaut inconnu"),
    (["outlier"], ["outlier=beaucoup"], "illisible"),
    (["outlier"], ["outlier=1.5"], "entre 0 et 1"),
    (["outlier"], ["fantome=0.1"], "défaut inconnu"),
])
def test_options_invalides(defauts, taux, message):
    with pytest.raises(ValueError, match=message):
        lire_options(defauts, taux)


# --- Sans défaut : rien ne change ----------------------------------------------

def test_sans_option_aucun_defaut(verite):
    actifs, taux = lire_options([], [])
    tables, bilan = injecter_defauts(verite, actifs, taux, RUN_DATE, GRAINE)
    assert bilan["lignes_injectees"].sum() == 0
    for nom in verite:
        pd.testing.assert_frame_equal(tables[nom], verite[nom])


def test_la_verite_n_est_pas_modifiee(verite, abime):
    assert len(verite["lignes_commande"]) == 10_000
    assert verite["lignes_commande"]["montant_xof"].dtype == "int64"
    assert verite["clients"]["nom_client"].notna().all()


# --- Chaque défaut est présent et compté ---------------------------------------

def test_doublons(abime):
    tables, bilan = abime
    lc = tables["lignes_commande"]
    assert lc.duplicated().sum() == _injectees(bilan, "doublon_ligne") == 500
    assert len(lc) == 10_500


def test_valeurs_manquantes(abime, verite):
    tables, bilan = abime
    for col in ["nom_client", "email", "ville"]:
        assert tables["clients"][col].isna().sum() == _injectees(bilan, "valeurs_manquantes", col) == 267
    sans_doublon = tables["lignes_commande"].drop_duplicates()
    assert sans_doublon["montant_xof"].isna().sum() == _injectees(bilan, "valeurs_manquantes", "montant_xof")


def test_dates_futures(abime):
    tables, bilan = abime
    futures = tables["commandes"]["date_commande"] > pd.Timestamp(RUN_DATE)
    assert futures.sum() == _injectees(bilan, "date_future") == 80


def test_montants_en_texte(abime):
    tables, bilan = abime
    montant = tables["lignes_commande"].drop_duplicates()["montant_xof"]
    texte = montant[montant.map(lambda v: isinstance(v, str))]
    assert len(texte) == _injectees(bilan, "montant_texte") == 300
    assert texte.str.fullmatch(r"\d{1,3}([ .]?\d{3})* (FCFA|F CFA|XOF)").all()


def test_outliers_et_quantites_negatives(abime):
    tables, bilan = abime
    lc = tables["lignes_commande"].drop_duplicates()
    assert (lc["prix_unitaire_xof"] == PRIX_OUTLIER).sum() == _injectees(bilan, "outlier") == 100
    assert (lc["quantite"] <= 0).sum() == _injectees(bilan, "quantite_negative") == 100


def test_defauts_de_lignes_sur_des_lignes_differentes(abime):
    lc = abime[0]["lignes_commande"].drop_duplicates()
    texte = lc["montant_xof"].map(lambda v: isinstance(v, str))
    marques = [lc["montant_xof"].isna(), texte, lc["prix_unitaire_xof"] == PRIX_OUTLIER, lc["quantite"] <= 0]
    assert (sum(m.astype(int) for m in marques) <= 1).all()


def test_encodage_abime(abime):
    tables, bilan = abime
    abimes = tables["clients"]["nom_client"].str.contains("Ã", na=False)
    assert abimes.sum() == _injectees(bilan, "encodage_nom") == 67
    # Le défaut est réparable : on retrouve le nom d'origine
    exemple = tables["clients"].loc[abimes, "nom_client"].iloc[0]
    assert "Ã" not in exemple.encode("latin-1").decode("utf-8")


def test_paiements_orphelins(abime):
    tables, bilan = abime
    orphelins = ~tables["paiements"]["commande_id"].isin(tables["commandes"]["commande_id"])
    assert orphelins.sum() == _injectees(bilan, "paiement_orphelin")
    assert tables["paiements"]["paiement_id"].is_unique


def test_bilan_proche_des_taux_demandes(abime):
    bilan = abime[1]
    lignes = bilan[bilan["taux_demande"] > 0]
    taux_obtenu = lignes["lignes_injectees"] / lignes["lignes_table_verite"]
    assert ((taux_obtenu - lignes["taux_demande"]).abs() <= 0.01).all()      # ±1 point


def test_meme_graine_memes_defauts(verite, abime):
    actifs, taux = lire_options(["tous"], [])
    tables, _ = injecter_defauts(verite, actifs, taux, RUN_DATE, GRAINE)
    pd.testing.assert_frame_equal(tables["lignes_commande"], abime[0]["lignes_commande"])


# --- Journal simulé -------------------------------------------------------------

def test_journal_simule(abime):
    tables = abime[0]
    journal = journal_simule(tables, RUN_DATE, GRAINE)
    format_ligne = r"2026-10-29 \d{2}:\d{2}:\d{2} (INFO|WARN|ERROR) ingestion: .+"
    assert all(re.fullmatch(format_ligne, ligne) for ligne in journal)
    assert sum(" ERROR " in ligne for ligne in journal) >= 2
    assert f"{len(tables['lignes_commande'])} lignes chargées depuis lignes_commande.csv" in "\n".join(journal)


# --- Défauts de fichier et ligne de commande ------------------------------------

def test_defauts_de_fichier(verite, tmp_path, monkeypatch):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    dossier = ecrire_brut(verite, RUN_DATE, defauts_fichier=["encodage_latin1", "colonne_manquante"])
    with pytest.raises(UnicodeDecodeError):
        (dossier / "clients.csv").read_text(encoding="utf-8")
    assert "quantite" not in pd.read_csv(dossier / "lignes_commande.csv", nrows=1).columns


def test_ligne_de_commande_complete(tmp_path, monkeypatch):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    assert main(["--run-date", RUN_DATE, "--rows", "2000", "--defauts", "tous"]) == 0
    dossier = tmp_path / "raw" / f"date={RUN_DATE}"
    assert (dossier / "bilan_generation.csv").exists()
    assert (dossier / "senmarket.log").exists()
    assert len(list(dossier.glob("*.csv"))) == 9            # 8 tables + le bilan


def test_ligne_de_commande_defaut_inconnu(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    assert main(["--run-date", RUN_DATE, "--defauts", "fantome"]) == 1
    assert "Défaut inconnu" in capsys.readouterr().err
    assert not (tmp_path / "raw").exists()
