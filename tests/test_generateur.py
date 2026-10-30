"""Invariants de la « vérité » : le jeu généré SANS défaut doit être parfaitement cohérent."""

import hashlib

import numpy as np
import pandas as pd
import pytest

from senmarket.generateur import COLONNES, calculer_graine, ecrire_brut, generer_verite, main

RUN_DATE = "2026-10-29"
JOURS = 365
FIN = pd.Timestamp(RUN_DATE)
DEBUT = FIN - pd.Timedelta(days=JOURS - 1)

CLES_PRIMAIRES = {
    "clients": "client_id", "vendeurs": "vendeur_id", "produits": "produit_id",
    "commandes": "commande_id", "lignes_commande": "ligne_commande_id", "paiements": "paiement_id",
    "avis": "avis_id", "navigation": "evenement_id",
}

# (table fille, colonne, table parente, facultatif ?)
CLES_ETRANGERES = [
    ("produits", "vendeur_id", "vendeurs", False),
    ("commandes", "client_id", "clients", False),
    ("lignes_commande", "commande_id", "commandes", False),
    ("lignes_commande", "produit_id", "produits", False),
    ("paiements", "commande_id", "commandes", False),
    ("avis", "client_id", "clients", False),
    ("avis", "produit_id", "produits", False),
    ("avis", "commande_id", "commandes", False),
    ("navigation", "client_id", "clients", True),
    ("navigation", "produit_id", "produits", True),
]


@pytest.fixture(scope="module")
def verite():
    return generer_verite(RUN_DATE, rows=5000, jours=JOURS, seed=42)


# --- Structure ----------------------------------------------------------------

def test_huit_tables_avec_les_colonnes_du_contrat(verite):
    assert set(verite) == set(COLONNES)
    for nom, colonnes in COLONNES.items():
        assert list(verite[nom].columns) == colonnes, nom


def test_volumes(verite):
    assert len(verite["lignes_commande"]) == 5000
    assert len(verite["commandes"]) == 2000          # N / 2,5
    assert len(verite["clients"]) == 1667            # N / 3
    assert len(verite["vendeurs"]) == 20
    assert len(verite["produits"]) == 40
    assert 8_000 <= len(verite["navigation"]) <= 12_000   # ≈ 2 N


def test_montants_en_entiers(verite):
    for table, col in [("produits", "prix_catalogue_xof"), ("lignes_commande", "prix_unitaire_xof"),
                       ("lignes_commande", "montant_xof"), ("paiements", "montant_xof")]:
        assert verite[table][col].dtype == np.int64, f"{table}.{col}"


# --- Clés ---------------------------------------------------------------------

@pytest.mark.parametrize("table, cle", CLES_PRIMAIRES.items())
def test_cles_primaires_uniques_et_presentes(verite, table, cle):
    serie = verite[table][cle]
    assert serie.notna().all()
    assert serie.is_unique
    assert serie.str.fullmatch(r"[A-Z]{3}\d{7}").all()


@pytest.mark.parametrize("fille, colonne, parente, facultatif", CLES_ETRANGERES)
def test_aucune_cle_etrangere_orpheline(verite, fille, colonne, parente, facultatif):
    valeurs = verite[fille][colonne]
    if facultatif:
        valeurs = valeurs.dropna()
    else:
        assert valeurs.notna().all()
    orphelines = ~valeurs.isin(verite[parente][CLES_PRIMAIRES[parente]])
    assert orphelines.sum() == 0


def test_un_produit_une_seule_fois_par_commande(verite):
    assert not verite["lignes_commande"].duplicated(["commande_id", "produit_id"]).any()


def test_au_plus_un_paiement_par_commande(verite):
    assert verite["paiements"]["commande_id"].is_unique


# --- Règles métier ------------------------------------------------------------

def test_montant_egal_quantite_fois_prix(verite):
    lc = verite["lignes_commande"]
    assert (lc["montant_xof"] == lc["quantite"] * lc["prix_unitaire_xof"]).all()


def test_quantites_et_prix_dans_les_plages(verite):
    lc = verite["lignes_commande"].merge(verite["produits"], on="produit_id")
    assert lc["quantite"].between(1, 5).all()
    assert verite["produits"]["prix_catalogue_xof"].between(1_000, 500_000).all()
    ratio = lc["prix_unitaire_xof"] / lc["prix_catalogue_xof"]
    assert ratio.between(0.9, 1.1).all()


def test_dates_dans_la_plage(verite):
    assert verite["commandes"]["date_commande"].between(DEBUT, FIN).all()
    assert (verite["clients"]["date_inscription"] <= FIN).all()
    assert (verite["paiements"]["date_paiement"] <= FIN).all()
    assert (verite["avis"]["date_avis"] <= FIN).all()
    assert (verite["navigation"]["date_evenement"] < FIN + pd.Timedelta(days=1)).all()


def test_commande_apres_inscription(verite):
    m = verite["commandes"].merge(verite["clients"], on="client_id")
    assert (m["date_commande"] >= m["date_inscription"]).all()


def test_paiement_et_avis_apres_la_commande(verite):
    p = verite["paiements"].merge(verite["commandes"], on="commande_id")
    assert (p["date_paiement"] >= p["date_commande"]).all()
    a = verite["avis"].merge(verite["commandes"], on="commande_id")
    assert (a["date_avis"] >= a["date_commande"]).all()


def test_avis_coherents_avec_leur_commande(verite):
    a = verite["avis"].merge(verite["commandes"], on="commande_id", suffixes=("", "_cmd"))
    assert (a["client_id"] == a["client_id_cmd"]).all()     # le client est celui de la commande
    assert (a["statut"] == "livree").all()                    # seulement des commandes livrées
    paires = verite["lignes_commande"][["commande_id", "produit_id"]].drop_duplicates()
    verif = verite["avis"].merge(paires, on=["commande_id", "produit_id"], how="left", indicator=True)
    assert (verif["_merge"] == "both").all()                  # le produit est dans la commande


def test_entonnoir_de_navigation_dans_l_ordre(verite):
    rang = {"vue_produit": 0, "ajout_panier": 1, "debut_paiement": 2}
    nav = verite["navigation"].sort_values(["session_id", "date_evenement", "evenement_id"])
    etapes = nav["type_evenement"].map(rang)
    # Au sein d'une session, l'étape ne recule jamais
    assert (etapes.groupby(nav["session_id"]).diff().dropna() >= 0).all()


# --- Réalisme -----------------------------------------------------------------

def test_realisme(verite):
    assert 0.25 <= (verite["clients"]["ville"] == "Dakar").mean() <= 0.40
    cmd_par_client = verite["commandes"]["client_id"].value_counts()
    assert (cmd_par_client >= 2).mean() >= 0.25               # des clients qui reviennent
    sessions = verite["navigation"].groupby("session_id")["type_evenement"]
    conversion = sessions.apply(lambda s: (s == "debut_paiement").any()).mean()
    assert 0.10 <= conversion <= 0.20                         # ≈ 15 %


# --- Reproductibilité et erreurs ----------------------------------------------

def test_meme_date_memes_donnees(verite):
    autre = generer_verite(RUN_DATE, rows=5000, jours=JOURS, seed=42)
    for nom in COLONNES:
        pd.testing.assert_frame_equal(verite[nom], autre[nom])


def test_autre_date_autres_donnees(verite):
    autre = generer_verite("2026-10-30", rows=5000, jours=JOURS, seed=42)
    assert not verite["clients"]["nom_client"].equals(autre["clients"]["nom_client"])


def test_graine_derivee_de_la_date():
    assert calculer_graine("2026-10-29", seed=42) == 4_220_261_029


@pytest.mark.parametrize("parametres, message", [
    ({"rows": 0}, "rows"),
    ({"jours": 0}, "jours"),
    ({"run_date": "29-10-2026"}, "AAAA-MM-JJ"),
])
def test_parametres_invalides(parametres, message):
    arguments = {"run_date": RUN_DATE, "rows": 100, "jours": 30} | parametres
    with pytest.raises(ValueError, match=message):
        generer_verite(**arguments)


# --- Écriture des fichiers bruts ----------------------------------------------

def _empreintes(dossier):
    return {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(dossier.glob("*.csv"))}


def test_ecrire_brut_produit_les_8_csv(verite, tmp_path, monkeypatch):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    dossier = ecrire_brut(verite, RUN_DATE)
    assert dossier == tmp_path / "raw" / f"date={RUN_DATE}"
    assert sorted(f.stem for f in dossier.glob("*.csv")) == sorted(COLONNES)
    commandes = pd.read_csv(dossier / "commandes.csv")
    assert commandes["date_commande"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
    assert list(commandes.columns) == COLONNES["commandes"]


def test_ecrire_brut_refuse_d_ecraser_sans_option(verite, tmp_path, monkeypatch):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    ecrire_brut(verite, RUN_DATE)
    with pytest.raises(FileExistsError, match="--ecraser"):
        ecrire_brut(verite, RUN_DATE)
    ecrire_brut(verite, RUN_DATE, ecraser=True)      # avec l'option, ça passe


def test_deux_executions_memes_empreintes(tmp_path, monkeypatch):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    premiere = _empreintes(ecrire_brut(generer_verite(RUN_DATE, rows=2000), RUN_DATE))
    seconde = _empreintes(ecrire_brut(generer_verite(RUN_DATE, rows=2000), RUN_DATE, ecraser=True))
    assert premiere == seconde


def test_ligne_de_commande_date_invalide(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    assert main(["--run-date", "29/10/2026"]) == 1
    assert "AAAA-MM-JJ" in capsys.readouterr().err
    assert not (tmp_path / "raw").exists()            # aucun dossier créé
