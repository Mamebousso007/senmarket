"""Tests du nettoyage : chaque fonction, les invariants, le rapprochement avec le bilan, l'épreuve."""

import pandas as pd
import pytest

from senmarket import nettoyage as n
from senmarket.generateur import main as generer

RUN_DATE = "2026-10-29"


# --- 1. Les fonctions, une par une ------------------------------------------

@pytest.mark.parametrize("brut, attendu", [
    ("37000", 37000),
    ("45 000 FCFA", 45000),
    ("45000 F CFA", 45000),
    ("45.000 XOF", 45000),        # le point est un séparateur de milliers, pas une virgule
    ("-64396", -64396),
])
def test_clean_montant(brut, attendu):
    assert n.clean_montant(pd.Series([brut])).iloc[0] == attendu


@pytest.mark.parametrize("brut", ["bonjour", "45 000 euros", None])
def test_clean_montant_illisible_ou_vide_devient_na(brut):
    assert pd.isna(n.clean_montant(pd.Series([brut])).iloc[0])


def test_clean_dates():
    dates = n.clean_dates(pd.Series(["2026-03-14", "14/03/2026", "2026-02-30", None]))
    assert dates.iloc[0] == pd.Timestamp("2026-03-14")
    assert dates.iloc[1:].isna().all()          # mauvais format, date impossible, vide


def test_clean_doublons_garde_la_premiere():
    df = pd.DataFrame({"id": ["A", "B", "A"], "v": [1, 2, 1]})
    assert n.clean_doublons(df).tolist() == [False, False, True]


def test_clean_encodage():
    repare = n.clean_encodage(pd.Series(["AÃ¯ssatou TourÃ©", "Cheikh Mbaye", None]))
    assert repare.tolist()[:2] == ["Aïssatou Touré", "Cheikh Mbaye"]
    assert pd.isna(repare.iloc[2])


def test_valider_cles():
    parents = pd.Series(["CLI1", "CLI2"])
    enfants = pd.Series(["CLI1", "CLI9", None])
    assert n.valider_cles(enfants, parents).tolist() == [False, True, True]
    assert n.valider_cles(enfants, parents, facultatif=True).tolist() == [False, True, False]


# --- 2. Une partition complète ------------------------------------------------

@pytest.fixture(scope="module")
def partition(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("donnees")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SENMARKET_DATA_DIR", str(dossier))
        assert generer(["--run-date", RUN_DATE, "--defauts", "tous"]) == 0
        brut = n.lire_brut(RUN_DATE)
        bilan_generation = pd.read_csv(dossier / "raw" / f"date={RUN_DATE}" / "bilan_generation.csv")
        resultat = n.nettoyer(brut, RUN_DATE)
        processed, rejected = n.ecrire_resultats(resultat, RUN_DATE)
    return brut, resultat, bilan_generation, processed, rejected


def _motif(resultat, table, motif):
    m = resultat["motifs"]
    return int(m[(m["table"] == table) & (m["motif"] == motif)]["lignes"].sum())


def _injecte(bilan, defaut, colonne=None):
    b = bilan[bilan["defaut"] == defaut]
    return int((b[b["colonne"] == colonne] if colonne else b)["lignes_injectees"].sum())


def test_brut_egal_accepte_plus_rejete(partition):
    _, resultat, *_ = partition
    b = resultat["bilan"]
    assert (b["brut"] == b["accepte"] + b["rejete"]).all()


def test_cles_primaires_uniques_et_aucune_orpheline(partition):
    _, resultat, *_ = partition
    acc = resultat["acceptes"]
    for nom, cle in n.CLES.items():
        assert acc[nom][cle].is_unique, nom
    for table, col, parente, facultatif in n.CLES_ETRANGERES:
        assert not n.valider_cles(acc[table][col], acc[parente][n.CLES[parente]], facultatif).any()


def test_aucune_date_future(partition):
    _, resultat, *_ = partition
    for nom, df in resultat["acceptes"].items():
        for col in [c for c in df.columns if c.startswith("date_")]:
            assert (df[col] < pd.Timestamp(RUN_DATE) + pd.Timedelta(days=1)).all(), f"{nom}.{col}"


def test_types_du_parquet(partition):
    *_, processed, _ = partition
    lc = pd.read_parquet(processed / "lignes_commande.parquet")
    assert lc[["quantite", "prix_unitaire_xof", "montant_xof"]].dtypes.eq("int64").all()
    assert (lc["montant_xof"] == lc["quantite"] * lc["prix_unitaire_xof"]).all()
    assert pd.api.types.is_datetime64_any_dtype(pd.read_parquet(processed / "commandes.parquet")["date_commande"])


def test_chaque_rejet_a_un_motif(partition):
    _, resultat, *_ = partition
    for df in resultat["rejetes"].values():
        assert df["raison_rejet"].notna().all() and (df["raison_rejet"] != "").all()


# --- 3. Rapprochement avec le bilan de génération -----------------------------

def test_rapprochement_rejets(partition):
    _, resultat, bilan, *_ = partition
    assert _motif(resultat, "lignes_commande", "doublon_exact") == _injecte(bilan, "doublon_ligne")
    assert _motif(resultat, "lignes_commande", "quantite_invalide") == _injecte(bilan, "quantite_negative")
    assert _motif(resultat, "lignes_commande", "prix_unitaire_outlier") == _injecte(bilan, "outlier")
    assert _motif(resultat, "commandes", "date_future:date_commande") == _injecte(bilan, "date_future")
    assert _motif(resultat, "lignes_commande", "montant_non_numerique") == 0   # tous les textes convertis


def test_rapprochement_corrections(partition):
    _, resultat, bilan, *_ = partition
    c = resultat["corrections"].set_index("correction")["lignes"]
    assert c["montant_xof texte converti en entier"] == _injecte(bilan, "montant_texte")
    assert c["montant_xof vide → recalculé (quantite × prix)"] == _injecte(bilan, "valeurs_manquantes", "montant_xof")
    assert c["nom_client réparé (encodage)"] == _injecte(bilan, "encodage_nom")
    assert c["ville vide → « Inconnue » (et region)"] == _injecte(bilan, "valeurs_manquantes", "ville")


def test_cascade_des_dates_futures(partition):
    _, resultat, *_ = partition
    commandes_rejetees = set(resultat["rejetes"]["commandes"]["commande_id"])
    lignes_acceptees = resultat["acceptes"]["lignes_commande"]
    assert not lignes_acceptees["commande_id"].isin(commandes_rejetees).any()
    assert _motif(resultat, "lignes_commande", "cle_etrangere_invalide:commande_id") > 0


def test_ecarts_metier_non_rejetes(partition):
    _, resultat, *_ = partition
    # Un paiement dont le montant diffère des lignes (frais, remise) n'est PAS un rejet
    assert not resultat["motifs"]["motif"].str.contains("montant_incoherent").any()


# --- 4. L'épreuve du fichier corrompu ----------------------------------------

@pytest.mark.parametrize("defaut, message", [
    ("colonne_manquante", "lignes_commande.csv : colonne(s) obligatoire(s) absente(s) : quantite"),
    ("encodage_latin1", "clients.csv n'est pas encodé en UTF-8"),
])
def test_fichier_corrompu_echec_propre(defaut, message, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    assert generer(["--run-date", RUN_DATE, "--rows", "1000", "--defauts", defaut]) == 0
    capsys.readouterr()
    assert n.main(["--run-date", RUN_DATE]) == 1                # code de retour non nul
    assert message in capsys.readouterr().err                   # message clair
    assert not (tmp_path / "processed").exists()                # aucune sortie à moitié écrite
    assert not (tmp_path / "rejected").exists()


def test_partition_inexistante(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    assert n.main(["--run-date", RUN_DATE]) == 1
    assert "Génère-la d'abord" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []
