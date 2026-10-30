"""Génération des données SenMarket.

Ce qui est fait :
- generer_verite() : la « vérité », un jeu de 8 tables parfaitement cohérent, en mémoire ;
- ecrire_brut()    : l'écriture des 8 CSV dans data/raw/date=AAAA-MM-JJ/.
À venir : l'injection contrôlée de défauts, le bilan et le journal simulé.

Lancer depuis le terminal :
    python -m senmarket.generateur --run-date 2026-10-29 --rows 10000 [--ecraser]

Principes :
- tout est vectorisé avec NumPy (pas de boucle sur les lignes), sauf les numéros de téléphone (Faker) ;
- une seule graine, dérivée de SENMARKET_SEED et de la date d'exécution : même date = mêmes données ;
- aucune date ne dépend de l'heure courante ;
- les identifiants sont attribués après un tri explicite (par date), donc toujours dans le même ordre.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

from senmarket import referentiels as ref
from senmarket.chemins import dossier_raw, valider_date

logger = logging.getLogger("senmarket.generateur")  # nom fixe, même lancé avec python -m

# Ordre des colonnes de chaque table, tel que défini dans docs/CONTRAT_DONNEES.md
COLONNES = {
    "clients": ["client_id", "nom_client", "email", "telephone", "ville", "region", "date_inscription"],
    "vendeurs": ["vendeur_id", "nom_vendeur", "ville", "region"],
    "produits": ["produit_id", "nom_produit", "categorie", "vendeur_id", "prix_catalogue_xof", "actif"],
    "commandes": ["commande_id", "client_id", "date_commande", "statut"],
    "lignes_commande": ["ligne_commande_id", "commande_id", "produit_id", "quantite",
                        "prix_unitaire_xof", "montant_xof"],
    "paiements": ["paiement_id", "commande_id", "methode_paiement", "statut_paiement",
                  "montant_xof", "date_paiement"],
    "avis": ["avis_id", "client_id", "produit_id", "commande_id", "note", "date_avis"],
    "navigation": ["evenement_id", "session_id", "client_id", "produit_id", "type_evenement",
                   "date_evenement"],
}

STATUTS_COMMANDE = np.array(["en_cours", "expediee", "livree", "annulee"])


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------

def calculer_graine(run_date: str, seed: int | None = None) -> int:
    """Graine dérivée de la graine de base et de la date : 42 et 2026-10-29 → 4 220 261 029.

    Pas de hash() Python : sa valeur change d'une session à l'autre.
    """
    run_date = valider_date(run_date)
    if seed is None:
        seed = int(os.getenv("SENMARKET_SEED", "42"))
    return seed * 100_000_000 + int(run_date.replace("-", ""))


def _valeurs_et_poids(liste):
    """[(valeur, poids), ...] → (tableau de valeurs, probabilités qui somment à 1)."""
    valeurs = np.array([v for v, _ in liste])
    poids = np.array([p for _, p in liste], dtype=float)
    return valeurs, poids / poids.sum()


def _identifiants(prefixe: str, n: int) -> np.ndarray:
    """CLI0000001, CLI0000002… (préfixe + 7 chiffres)."""
    return (prefixe + pd.Series(np.arange(1, n + 1)).astype(str).str.zfill(7)).to_numpy()


def _jour_entre(rng, debut: np.ndarray, fin: np.datetime64) -> np.ndarray:
    """Un jour tiré uniformément entre debut (tableau) et fin (inclus), pour chaque élément."""
    ecart = (fin - debut).astype(int)
    return debut + np.floor(rng.random(len(debut)) * (ecart + 1)).astype(int)


def _sans_accents(serie: pd.Series) -> pd.Series:
    return serie.str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii")


# ---------------------------------------------------------------------------
# La vérité
# ---------------------------------------------------------------------------

def generer_verite(run_date: str, rows: int = 10_000, jours: int = 365,
                   seed: int | None = None) -> dict[str, pd.DataFrame]:
    """Génère les 8 tables cohérentes. `rows` = nombre de lignes de commande."""
    if rows < 10:
        raise ValueError(f"rows doit valoir au moins 10 (reçu : {rows}).")
    if jours < 1:
        raise ValueError(f"jours doit valoir au moins 1 (reçu : {jours}).")

    graine = calculer_graine(run_date, seed)
    rng = np.random.default_rng(graine)
    fake = Faker("fr_FR")
    fake.seed_instance(graine)

    fin = np.datetime64(run_date, "D")
    debut = fin - (jours - 1)                     # les commandes couvrent [debut, fin]
    logger.info("Génération de la vérité : %s lignes, du %s au %s", rows, debut, fin)

    villes = np.array([v for v, _, _ in ref.VILLES])
    regions = np.array([r for _, r, _ in ref.VILLES])
    p_villes = np.array([p for _, _, p in ref.VILLES]) / sum(p for _, _, p in ref.VILLES)

    # --- vendeurs -----------------------------------------------------------
    nb_v = ref.NB_VENDEURS
    i_ville = rng.choice(len(villes), size=nb_v, p=p_villes)
    noms_v = rng.choice(ref.NOMS, size=nb_v, replace=False)
    prefixes_v = rng.choice(ref.PREFIXES_BOUTIQUE, size=nb_v)
    vendeurs = pd.DataFrame({
        "vendeur_id": _identifiants("VEN", nb_v),
        "nom_vendeur": pd.Series(prefixes_v) + " " + pd.Series(noms_v),
        "ville": villes[i_ville],
        "region": regions[i_ville],
    })

    # --- produits -----------------------------------------------------------
    nb_p = len(ref.PRODUITS)
    prix_catalogue = np.array([p for _, _, p in ref.PRODUITS], dtype=np.int64)
    produits = pd.DataFrame({
        "produit_id": _identifiants("PRD", nb_p),
        "nom_produit": [n for n, _, _ in ref.PRODUITS],
        "categorie": [c for _, c, _ in ref.PRODUITS],
        "vendeur_id": rng.choice(vendeurs["vendeur_id"].to_numpy(), size=nb_p),
        "prix_catalogue_xof": prix_catalogue,
        "actif": rng.random(nb_p) < 0.9,
    })
    # Popularité de type Zipf : le produit de rang k est tiré avec un poids 1 / k^1.1
    rangs = rng.permutation(nb_p) + 1
    p_produits = 1 / rangs ** 1.1
    p_produits /= p_produits.sum()

    # --- clients ------------------------------------------------------------
    nb_c = max(1, round(rows / 3))
    i_ville = rng.choice(len(villes), size=nb_c, p=p_villes)
    prenoms = pd.Series(rng.choice(ref.PRENOMS, size=nb_c))
    noms = pd.Series(rng.choice(ref.NOMS, size=nb_c))
    domaines, p_domaines = _valeurs_et_poids(ref.DOMAINES_EMAIL)
    email = (
        _sans_accents(prenoms).str.lower().str.replace(" ", "", regex=False) + "."
        + _sans_accents(noms).str.lower() + pd.Series(rng.integers(1, 1000, size=nb_c)).astype(str)
        + "@" + pd.Series(rng.choice(domaines, size=nb_c, p=p_domaines))
    )
    prefixes_tel = rng.choice(ref.PREFIXES_TELEPHONE, size=nb_c)
    telephone = [f"+221 {p} " + fake.numerify("### ## ##") for p in prefixes_tel]
    clients = pd.DataFrame({
        "nom_client": prenoms + " " + noms,
        "email": email,
        "telephone": telephone,
        "ville": villes[i_ville],
        "region": regions[i_ville],
        "date_inscription": fin - rng.integers(0, jours + 730, size=nb_c),
        # Activité : quelques gros clients, beaucoup de petits (loi log-normale)
        "_activite": rng.lognormal(mean=0.0, sigma=1.2, size=nb_c),
    })
    clients = clients.sort_values("date_inscription", kind="stable").reset_index(drop=True)
    clients.insert(0, "client_id", _identifiants("CLI", nb_c))
    activite = clients.pop("_activite").to_numpy()
    p_clients = activite / activite.sum()
    inscription = clients["date_inscription"].to_numpy().astype("datetime64[D]")

    # --- commandes ----------------------------------------------------------
    nb_cmd = max(1, round(rows / 2.5))
    i_client = rng.choice(nb_c, size=nb_cmd, p=p_clients)
    date_cmd = _jour_entre(rng, np.maximum(inscription[i_client], debut), fin)

    age = (fin - date_cmd).astype(int)
    statut = np.empty(nb_cmd, dtype=object)
    for masque, probas in [
        (age <= 3, [0.50, 0.40, 0.05, 0.05]),
        ((age > 3) & (age <= 14), [0.10, 0.30, 0.55, 0.05]),
        (age > 14, [0.00, 0.00, 0.92, 0.08]),
    ]:
        statut[masque] = rng.choice(STATUTS_COMMANDE, size=masque.sum(), p=probas)

    ordre = np.lexsort((i_client, date_cmd))      # tri par date, puis par client
    i_client, date_cmd, statut = i_client[ordre], date_cmd[ordre], statut[ordre]
    commandes = pd.DataFrame({
        "commande_id": _identifiants("CMD", nb_cmd),
        "client_id": clients["client_id"].to_numpy()[i_client],
        "date_commande": date_cmd,
        "statut": statut.astype(str),
    })

    # --- lignes de commande -------------------------------------------------
    # Chaque commande a au moins une ligne ; les lignes restantes sont réparties au hasard
    nb_lignes = 1 + np.bincount(rng.integers(0, nb_cmd, size=rows - nb_cmd), minlength=nb_cmd)
    i_cmd = np.repeat(np.arange(nb_cmd), nb_lignes)
    i_produit = rng.choice(nb_p, size=rows, p=p_produits)
    # Un même produit n'apparaît qu'une fois par commande : on retire les doublons jusqu'à n'en avoir plus
    for _ in range(100):
        doublon = pd.DataFrame({"cmd": i_cmd, "prd": i_produit}).duplicated().to_numpy()
        if not doublon.any():
            break
        i_produit[doublon] = rng.choice(nb_p, size=int(doublon.sum()), p=p_produits)
    else:
        raise RuntimeError("Impossible d'obtenir des produits distincts dans chaque commande.")
    valeurs_q, p_q = _valeurs_et_poids(ref.QUANTITES)
    quantite = rng.choice(valeurs_q, size=rows, p=p_q).astype(np.int64)

    cat = prix_catalogue[i_produit]
    promo = rng.random(rows) < 0.30                # 30 % des lignes à un prix différent du catalogue
    facteur = np.where(promo, rng.uniform(0.90, 1.10, size=rows), 1.0)
    prix_unitaire = np.clip(np.round(cat * facteur), np.ceil(cat * 0.9), np.floor(cat * 1.1)).astype(np.int64)
    montant = quantite * prix_unitaire

    lignes = pd.DataFrame({
        "ligne_commande_id": _identifiants("LIG", rows),
        "commande_id": commandes["commande_id"].to_numpy()[i_cmd],
        "produit_id": produits["produit_id"].to_numpy()[i_produit],
        "quantite": quantite,
        "prix_unitaire_xof": prix_unitaire,
        "montant_xof": montant,
    })

    # --- paiements ----------------------------------------------------------
    total_cmd = np.bincount(i_cmd, weights=montant, minlength=nb_cmd).astype(np.int64)
    a_paiement = rng.random(nb_cmd) >= 0.02        # ~2 % de commandes sans paiement (réalisme métier)
    j = np.flatnonzero(a_paiement)
    methodes, p_m = _valeurs_et_poids(ref.METHODES_PAIEMENT)
    statuts_p, p_s = _valeurs_et_poids(ref.STATUTS_PAIEMENT)
    montant_paye = total_cmd[j].copy()
    ecart = rng.random(len(j)) < 0.01              # ~1 % d'écarts volontaires (frais ou remise)
    frais = rng.integers(5, 21, size=len(j)) * 100
    remise = -np.round(montant_paye * 0.05).astype(np.int64)
    montant_paye = np.where(ecart, montant_paye + np.where(rng.random(len(j)) < 0.5, frais, remise),
                            montant_paye)
    paiements = pd.DataFrame({
        "paiement_id": _identifiants("PAI", len(j)),
        "commande_id": commandes["commande_id"].to_numpy()[j],
        "methode_paiement": rng.choice(methodes, size=len(j), p=p_m),
        "statut_paiement": rng.choice(statuts_p, size=len(j), p=p_s),
        "montant_xof": montant_paye.astype(np.int64),
        "date_paiement": np.minimum(date_cmd[j] + rng.integers(0, 3, size=len(j)), fin),
    })

    # --- avis ---------------------------------------------------------------
    # ~10 % des LIGNES des commandes livrées reçoivent un avis (voir le point ouvert du contrat)
    choisies = np.flatnonzero((statut[i_cmd] == "livree") & (rng.random(rows) < 0.10))
    i_cmd_avis = i_cmd[choisies]
    avis = pd.DataFrame({
        "avis_id": _identifiants("AVI", len(choisies)),
        "client_id": commandes["client_id"].to_numpy()[i_cmd_avis],
        "produit_id": lignes["produit_id"].to_numpy()[choisies],
        "commande_id": commandes["commande_id"].to_numpy()[i_cmd_avis],
        "note": rng.choice([1, 2, 3, 4, 5], size=len(choisies), p=[0.05, 0.07, 0.13, 0.35, 0.40]),
        "date_avis": np.minimum(date_cmd[i_cmd_avis] + rng.integers(1, 31, size=len(choisies)), fin),
    })

    # --- navigation ---------------------------------------------------------
    # Une session : 1 à 6 vues, puis éventuellement un ajout au panier, puis un début de paiement
    nb_sess = max(1, round(2 * rows / 2.5))       # ≈ 2,5 événements par session → ≈ 2 N événements
    nb_vues = np.minimum(rng.geometric(0.5, size=nb_sess), 6)
    ajout = rng.random(nb_sess) < 0.35
    paiement = ajout & (rng.random(nb_sess) < 0.15 / 0.35)   # ≈ 15 % des sessions au total
    nb_evt = nb_vues + ajout + paiement

    anonyme = rng.random(nb_sess) < 0.30
    i_client_s = rng.choice(nb_c, size=nb_sess, p=p_clients)
    jour_min = np.where(anonyme, debut, np.maximum(inscription[i_client_s], debut))
    debut_sess = (_jour_entre(rng, jour_min, fin).astype("datetime64[s]")
                  + rng.integers(0, 22 * 3600, size=nb_sess))

    total = int(nb_evt.sum())
    i_sess = np.repeat(np.arange(nb_sess), nb_evt)
    premier = np.cumsum(nb_evt) - nb_evt               # position du premier événement de chaque session
    position = np.arange(total) - premier[i_sess]
    type_evt = np.where(position < nb_vues[i_sess], "vue_produit",
                        np.where(position == nb_vues[i_sess], "ajout_panier", "debut_paiement"))

    pas = rng.integers(10, 301, size=total)            # 10 s à 5 min entre deux événements
    pas[premier] = 0
    cumul = np.cumsum(pas)
    horodatage = debut_sess[i_sess] + (cumul - cumul[premier][i_sess])

    produit_evt = rng.choice(nb_p, size=total, p=p_produits)
    derniere_vue = premier + nb_vues - 1               # l'ajout et le paiement portent sur la dernière vue
    produit_evt = np.where(position >= nb_vues[i_sess], produit_evt[derniere_vue][i_sess], produit_evt)

    rang_sess = np.empty(nb_sess, dtype=np.int64)      # sessions numérotées dans l'ordre chronologique
    rang_sess[np.argsort(debut_sess, kind="stable")] = np.arange(nb_sess)
    navigation = pd.DataFrame({
        "session_id": _identifiants("SES", nb_sess)[rang_sess[i_sess]],
        "client_id": pd.Series(clients["client_id"].to_numpy()[i_client_s][i_sess]).where(~anonyme[i_sess]),
        "produit_id": produits["produit_id"].to_numpy()[produit_evt],
        "type_evenement": type_evt,
        "date_evenement": horodatage,
        "_position": position,
    })
    navigation = (navigation.sort_values(["date_evenement", "session_id", "_position"], kind="stable")
                  .drop(columns="_position").reset_index(drop=True))
    navigation.insert(0, "evenement_id", _identifiants("NAV", total))

    tables = {
        "clients": clients, "vendeurs": vendeurs, "produits": produits, "commandes": commandes,
        "lignes_commande": lignes, "paiements": paiements, "avis": avis, "navigation": navigation,
    }
    for nom, colonnes in COLONNES.items():
        tables[nom] = tables[nom][colonnes].reset_index(drop=True)
        logger.info("Vérité : %-16s %8d lignes", nom, len(tables[nom]))
    return tables


# ---------------------------------------------------------------------------
# Écriture des fichiers bruts
# ---------------------------------------------------------------------------

CLES_PRIMAIRES = {nom: colonnes[0] for nom, colonnes in COLONNES.items()}
HORODATAGES = {"date_evenement"}          # les autres colonnes date_* sont des dates sans heure


def _preparer_pour_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Trie par clé primaire et écrit les dates au format du contrat (AAAA-MM-JJ)."""
    df = df.sort_values(df.columns[0], kind="stable").copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            format_date = "%Y-%m-%d %H:%M:%S" if col in HORODATAGES else "%Y-%m-%d"
            df[col] = df[col].dt.strftime(format_date)
    return df


def ecrire_brut(tables: dict[str, pd.DataFrame], run_date: str, ecraser: bool = False) -> Path:
    """Écrit les 8 tables en CSV UTF-8 dans data/raw/date=AAAA-MM-JJ/ et renvoie ce dossier.

    On écrit d'abord dans un dossier temporaire, puis on le renomme : en cas d'erreur
    au milieu, aucun dossier « à moitié écrit » ne reste dans data/raw/.
    """
    destination = dossier_raw(run_date)
    if destination.exists() and not ecraser:
        raise FileExistsError(
            f"La partition brute {destination} existe déjà. "
            "Relance avec --ecraser pour la remplacer."
        )

    temporaire = destination.with_name(f".en_cours_{destination.name}")
    shutil.rmtree(temporaire, ignore_errors=True)
    temporaire.mkdir(parents=True)
    try:
        for nom in COLONNES:
            _preparer_pour_csv(tables[nom]).to_csv(
                temporaire / f"{nom}.csv", index=False, encoding="utf-8", lineterminator="\n"
            )
        if destination.exists():
            shutil.rmtree(destination)
        temporaire.rename(destination)
    except Exception:
        shutil.rmtree(temporaire, ignore_errors=True)
        raise

    logger.info("8 fichiers CSV écrits dans %s", destination)
    return destination


# ---------------------------------------------------------------------------
# Ligne de commande
# ---------------------------------------------------------------------------

def main(arguments: list[str] | None = None) -> int:
    from senmarket.journal import configurer_logging

    parseur = argparse.ArgumentParser(description="Génère les données SenMarket dans data/raw/.")
    parseur.add_argument("--run-date", required=True, help="date d'exécution, format AAAA-MM-JJ")
    parseur.add_argument("--rows", type=int, default=10_000, help="nombre de lignes de commande")
    parseur.add_argument("--jours", type=int, default=365, help="nombre de jours couverts")
    parseur.add_argument("--ecraser", action="store_true", help="remplace une partition existante")
    args = parseur.parse_args(arguments)

    try:
        configurer_logging(args.run_date)
        tables = generer_verite(args.run_date, rows=args.rows, jours=args.jours)
        ecrire_brut(tables, args.run_date, ecraser=args.ecraser)
    except (ValueError, FileExistsError) as erreur:
        logger.error("%s", erreur)
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
