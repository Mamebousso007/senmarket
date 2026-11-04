"""Nettoyage des données SenMarket (chapitre 4, ticket SM-005).

Trois traitements possibles pour chaque problème :
- CORRIGER  : conversion de type, réparation d'encodage, recalcul d'un montant ;
- ÉTIQUETER : une valeur manquante remplacée par « Inconnue » / « Inconnu » ;
- METTRE EN QUARANTAINE : la ligne est écartée AVEC son motif (raison_rejet), jamais effacée.

Organisation du fichier :
1. Les fonctions de nettoyage (une responsabilité chacune, aucune lecture ni écriture de fichier) ;
2. La validation d'une table : calcul des motifs de rejet ;
3. nettoyer() : les 8 tables dans l'ordre, avec la cascade des clés étrangères ;
4. Lecture de la partition brute (avec échec propre) et écriture des résultats ;
5. La ligne de commande : python -m senmarket.nettoyage --run-date 2026-10-29
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from senmarket.chemins import dossier_processed, dossier_raw, dossier_rejected
from senmarket.export import exporter_jsonl
from senmarket.generateur import COLONNES

logger = logging.getLogger("senmarket.nettoyage")

ORDRE = ["clients", "vendeurs", "produits", "commandes", "lignes_commande", "paiements", "avis", "navigation"]
CLES = {nom: colonnes[0] for nom, colonnes in COLONNES.items()}
PRIX_MAX = 1_000_000
HORODATAGES = {"date_evenement"}

VALEURS_PERMISES = {
    ("commandes", "statut"): {"livree", "expediee", "en_cours", "annulee"},
    ("paiements", "methode_paiement"): {"wave", "orange_money", "carte", "especes"},
    ("paiements", "statut_paiement"): {"reussi", "echoue", "en_attente"},
    ("navigation", "type_evenement"): {"vue_produit", "ajout_panier", "debut_paiement"},
    ("produits", "categorie"): {"telephonie", "mode_tissus", "alimentation", "maison",
                                "electromenager", "beaute", "informatique"},
}

# (table, colonne, table parente, facultatif ?)
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

# Colonnes facultatives : peuvent rester vides sans rejet
FACULTATIVES = {("clients", "email"), ("clients", "telephone"),
                ("navigation", "client_id"), ("navigation", "produit_id")}


class ErreurFichier(Exception):
    """Un fichier d'entrée est inutilisable : on arrête tout, proprement, avec un message clair."""


# ---------------------------------------------------------------------------
# 1. Les fonctions de nettoyage
# ---------------------------------------------------------------------------

def clean_montant(serie: pd.Series) -> pd.Series:
    """Convertit les montants bruts (« 45 000 FCFA », « 45000 F CFA », « 45.000 XOF ») en entiers.

    Ce qui reste illisible devient vide (<NA>) : c'est à l'appelant de décider quoi en faire.
    On peut retirer les points sans risque : le franc CFA n'a pas de centimes.
    """
    texte = serie.astype("str")
    for mot in ["F CFA", "FCFA", "XOF"]:          # « F CFA » d'abord, sinon « FCFA » ne le reconnaît pas
        texte = texte.str.replace(mot, "", regex=False)
    texte = texte.str.replace(" ", "", regex=False).str.replace(".", "", regex=False)
    return pd.to_numeric(texte, errors="coerce").astype("Int64")


def clean_dates(serie: pd.Series, avec_heure: bool = False) -> pd.Series:
    """Convertit des dates texte au format du contrat ; une date illisible devient NaT."""
    format_date = "%Y-%m-%d %H:%M:%S" if avec_heure else "%Y-%m-%d"
    return pd.to_datetime(serie, format=format_date, errors="coerce")


def clean_doublons(df: pd.DataFrame) -> pd.Series:
    """Vrai pour chaque COPIE exacte d'une ligne déjà vue (la première occurrence est gardée)."""
    return df.duplicated(keep="first")


def clean_encodage(serie: pd.Series) -> pd.Series:
    """Répare le texte UTF-8 lu par erreur comme du Latin-1 (« AÃ¯ssatou » → « Aïssatou »)."""
    def reparer(texte):
        if not isinstance(texte, str) or ("Ã" not in texte and "Â" not in texte):
            return texte
        try:
            return texte.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return texte                              # irréparable : on laisse tel quel
    return serie.map(reparer)


def valider_cles(serie: pd.Series, cles_parentes: pd.Series, facultatif: bool = False) -> pd.Series:
    """Vrai pour chaque clé étrangère invalide : absente de la table parente ACCEPTÉE."""
    invalide = ~serie.isin(cles_parentes)
    if facultatif:
        invalide &= serie.notna()                     # une clé facultative vide n'est pas une erreur
    return invalide


# ---------------------------------------------------------------------------
# 2. Validation d'une table
# ---------------------------------------------------------------------------

class Motifs:
    """Accumule les motifs de rejet d'une table ; une ligne peut en cumuler plusieurs (séparés par ;)."""

    def __init__(self, index):
        self.raison = pd.Series("", index=index, dtype="str")

    def ajouter(self, masque, motif):
        masque = pd.Series(masque, index=self.raison.index).fillna(False).astype(bool)
        self.raison = self.raison.where(~masque, self.raison + ";" + motif)

    @property
    def rejetees(self):
        return self.raison != ""

    def texte(self):
        return self.raison.str.lstrip(";")


def _valider(nom: str, df: pd.DataFrame, acceptes: dict[str, pd.DataFrame],
             run_date: pd.Timestamp, corrections: list) -> tuple[pd.DataFrame, pd.Series]:
    """Corrige et valide une table (déjà sans doublons exacts). Renvoie (table corrigée, motifs)."""
    df = df.copy()
    motifs = Motifs(df.index)
    cle = CLES[nom]

    def corriger(quoi, nombre):
        corrections.append({"table": nom, "correction": quoi, "lignes": int(nombre)})

    # --- corrections et étiquetage, spécifiques à chaque table --------------
    if nom == "clients":
        abime = df["nom_client"].str.contains("Ã|Â", na=False)
        df["nom_client"] = clean_encodage(df["nom_client"])
        corriger("nom_client réparé (encodage)", abime.sum())
        corriger("nom_client vide → « Inconnu »", df["nom_client"].isna().sum())
        df["nom_client"] = df["nom_client"].fillna("Inconnu")
        sans_ville = df["ville"].isna()
        corriger("ville vide → « Inconnue » (et region)", sans_ville.sum())
        df.loc[sans_ville, ["ville", "region"]] = "Inconnue"

    if nom == "lignes_commande":
        quantite = pd.to_numeric(df["quantite"], errors="coerce").astype("Int64")
        prix = pd.to_numeric(df["prix_unitaire_xof"], errors="coerce").astype("Int64")
        montant = clean_montant(df["montant_xof"])
        etait_texte = df["montant_xof"].notna() & pd.to_numeric(df["montant_xof"], errors="coerce").isna()
        corriger("montant_xof texte converti en entier", (etait_texte & montant.notna()).sum())
        motifs.ajouter(df["montant_xof"].notna() & montant.isna(), "montant_non_numerique")
        a_recalculer = df["montant_xof"].isna() & quantite.notna() & prix.notna()
        corriger("montant_xof vide → recalculé (quantite × prix)", a_recalculer.sum())
        montant = montant.where(~a_recalculer, quantite * prix)
        motifs.ajouter(quantite.isna() | (quantite <= 0), "quantite_invalide")
        motifs.ajouter(prix.isna() | (prix <= 0), "prix_unitaire_invalide")
        motifs.ajouter(prix > PRIX_MAX, "prix_unitaire_outlier")
        motifs.ajouter(montant.notna() & quantite.notna() & prix.notna() & (montant != quantite * prix),
                       "montant_incoherent")
        df["quantite"], df["prix_unitaire_xof"], df["montant_xof"] = quantite, prix, montant

    if nom == "produits":
        prix = pd.to_numeric(df["prix_catalogue_xof"], errors="coerce").astype("Int64")
        motifs.ajouter(prix.isna() | (prix <= 0), "prix_catalogue_non_positif_ou_invalide")
        motifs.ajouter(prix > PRIX_MAX, "prix_catalogue_outlier")
        df["prix_catalogue_xof"] = prix
        df["actif"] = df["actif"].map({"True": True, "False": False})
        motifs.ajouter(df["actif"].isna(), "champ_obligatoire_absent:actif")

    if nom == "paiements":
        montant = clean_montant(df["montant_xof"])
        motifs.ajouter(df["montant_xof"].notna() & montant.isna(), "montant_non_numerique")
        motifs.ajouter(montant < 0, "montant_paiement_invalide")
        df["montant_xof"] = montant

    if nom == "avis":
        note = pd.to_numeric(df["note"], errors="coerce").astype("Int64")
        motifs.ajouter(df["note"].notna() & (note.isna() | ~note.between(1, 5)), "note_hors_intervalle")
        df["note"] = note

    # --- règles communes ------------------------------------------------------
    # Clé primaire : présente, et unique (sinon conflit : toutes les occurrences sont rejetées)
    motifs.ajouter(df[cle].isna(), f"cle_primaire_absente:{cle}")
    motifs.ajouter(df[cle].notna() & df[cle].duplicated(keep=False), f"cle_primaire_conflit:{cle}")

    # Champs obligatoires (hors clé primaire, déjà traitée)
    for col in COLONNES[nom][1:]:
        if (nom, col) not in FACULTATIVES:
            motifs.ajouter(df[col].isna(), f"champ_obligatoire_absent:{col}")

    # Valeurs hors liste (décision du projet, motif ajouté au catalogue du module)
    for (table, col), permises in VALEURS_PERMISES.items():
        if table == nom:
            motifs.ajouter(df[col].notna() & ~df[col].isin(permises), f"valeur_hors_liste:{col}")

    # Dates : lisibles et non futures
    for col in [c for c in COLONNES[nom] if c.startswith("date_")]:
        avec_heure = col in HORODATAGES
        dates = clean_dates(df[col], avec_heure=avec_heure)
        motifs.ajouter(df[col].notna() & dates.isna(), f"date_invalide:{col}")
        limite = run_date + pd.Timedelta(days=1) if avec_heure else run_date
        motifs.ajouter(dates >= limite if avec_heure else dates > limite, f"date_future:{col}")
        df[col] = dates

    # Clés étrangères : la ligne parente doit exister ET avoir été acceptée (effet cascade)
    for table, col, parente, facultatif in CLES_ETRANGERES:
        if table == nom:
            invalide = valider_cles(df[col], acceptes[parente][CLES[parente]], facultatif)
            motifs.ajouter(invalide, f"cle_etrangere_invalide:{col}")

    return df, motifs.texte()


# ---------------------------------------------------------------------------
# 3. Nettoyer les 8 tables
# ---------------------------------------------------------------------------

def _typer(nom: str, df: pd.DataFrame) -> pd.DataFrame:
    """Types propres pour les lignes acceptées : entiers sans vide → int64."""
    df = df.copy()
    for col in df.columns:
        if str(df[col].dtype) == "Int64" and df[col].notna().all():
            df[col] = df[col].astype("int64")
    if nom == "produits":
        df["actif"] = df["actif"].astype(bool)
    return df


def nettoyer(brut: dict[str, pd.DataFrame], run_date: str) -> dict:
    """Nettoie les 8 tables dans l'ordre parents → enfants. Aucune lecture ni écriture de fichier.

    Renvoie un dictionnaire : acceptes, rejetes (avec raison_rejet), bilan, motifs, corrections.
    """
    date = pd.Timestamp(run_date)
    acceptes, rejetes, bilan, corrections = {}, {}, [], []

    for nom in ORDRE:
        df = brut[nom].reset_index(drop=True)

        # 1) Les copies exactes sont écartées d'abord : on ne valide que des lignes uniques
        copie = clean_doublons(df)
        rejet_doublons = df[copie].assign(raison_rejet="doublon_exact")
        uniques = df[~copie]

        # 2) Correction, étiquetage et validation des lignes restantes
        corrige, raison = _valider(nom, uniques, acceptes, date, corrections)
        ok = raison == ""
        acceptes[nom] = _typer(nom, corrige[ok]).reset_index(drop=True)
        rejet_regles = uniques[~ok].assign(raison_rejet=raison[~ok])
        rejetes[nom] = pd.concat([rejet_regles, rejet_doublons]).sort_index().reset_index(drop=True)

        bilan.append({"table": nom, "brut": len(df), "accepte": len(acceptes[nom]),
                      "rejete": len(rejetes[nom])})
        logger.info("%-16s brut %7d | accepté %7d | rejeté %6d",
                    nom, len(df), len(acceptes[nom]), len(rejetes[nom]))

    motifs = (pd.concat([r.assign(table=n)[["table", "raison_rejet"]] for n, r in rejetes.items()])
              .assign(motif=lambda d: d["raison_rejet"].str.split(";")).explode("motif")
              .groupby(["table", "motif"]).size().rename("lignes").reset_index())
    return {"acceptes": acceptes, "rejetes": rejetes, "bilan": pd.DataFrame(bilan),
            "motifs": motifs, "corrections": pd.DataFrame(corrections)}


# ---------------------------------------------------------------------------
# 4. Lecture et écriture
# ---------------------------------------------------------------------------

def lire_brut(run_date: str) -> dict[str, pd.DataFrame]:
    """Lit les 8 CSV bruts EN TEXTE (on convertit nous-mêmes, sans laisser Pandas deviner).

    Échec propre (ErreurFichier) si la partition, un fichier, une colonne ou l'encodage pose problème.
    """
    dossier = dossier_raw(run_date)
    if not dossier.is_dir():
        raise ErreurFichier(
            f"La partition brute {dossier} n'existe pas. Génère-la d'abord :\n"
            f"  python -m senmarket.generateur --run-date {run_date} --defauts tous"
        )
    tables = {}
    for nom in ORDRE:
        chemin = dossier / f"{nom}.csv"
        if not chemin.exists():
            raise ErreurFichier(f"Fichier manquant : {chemin}")
        try:
            df = pd.read_csv(chemin, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8")
        except UnicodeDecodeError:
            raise ErreurFichier(
                f"{chemin.name} n'est pas encodé en UTF-8 (il contient des octets invalides). "
                f"Régénère la partition, ou convertis le fichier : iconv -f latin1 -t utf-8"
            ) from None
        manquantes = [c for c in COLONNES[nom] if c not in df.columns]
        if manquantes:
            raise ErreurFichier(f"{chemin.name} : colonne(s) obligatoire(s) absente(s) : {', '.join(manquantes)}")
        tables[nom] = df[COLONNES[nom]]
    return tables


def _pour_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Dates au format du contrat (AAAA-MM-JJ), tri par clé primaire."""
    df = df.sort_values(df.columns[0], kind="stable").copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S" if col in HORODATAGES else "%Y-%m-%d")
    return df


def ecrire_resultats(resultat: dict, run_date: str) -> tuple[Path, Path]:
    """Écrit processed/ et rejected/ ; tout est d'abord écrit à côté, puis renommé d'un coup."""
    sorties = {"processed": dossier_processed(run_date), "rejected": dossier_rejected(run_date)}
    temporaires = {k: v.with_name(f".en_cours_{v.name}") for k, v in sorties.items()}
    try:
        for t in temporaires.values():
            shutil.rmtree(t, ignore_errors=True)
            t.mkdir(parents=True)
        (temporaires["processed"] / "json").mkdir()
        for nom, df in resultat["acceptes"].items():
            df = df.sort_values(CLES[nom], kind="stable")
            df.to_parquet(temporaires["processed"] / f"{nom}.parquet", index=False)
            texte = _pour_csv(df)
            texte.to_csv(temporaires["processed"] / f"{nom}.csv", index=False, lineterminator="\n")
            exporter_jsonl(texte, temporaires["processed"] / "json" / f"{nom}.jsonl")
        for nom, df in resultat["rejetes"].items():
            df.to_csv(temporaires["rejected"] / f"{nom}_rejetes.csv", index=False, lineterminator="\n")
        for fichier in ["bilan", "motifs", "corrections"]:
            nom_fichier = {"bilan": "bilan_nettoyage", "motifs": "motifs_rejet", "corrections": "corrections"}[fichier]
            resultat[fichier].to_csv(temporaires["rejected"] / f"{nom_fichier}.csv", index=False,
                                     lineterminator="\n")
        for cle, destination in sorties.items():
            shutil.rmtree(destination, ignore_errors=True)
            temporaires[cle].rename(destination)
    except Exception:
        for t in temporaires.values():
            shutil.rmtree(t, ignore_errors=True)
        raise
    logger.info("Résultats écrits dans %s et %s", sorties["processed"], sorties["rejected"])
    return sorties["processed"], sorties["rejected"]


# ---------------------------------------------------------------------------
# 5. Ligne de commande
# ---------------------------------------------------------------------------

def main(arguments: list[str] | None = None) -> int:
    from senmarket.journal import configurer_logging

    parseur = argparse.ArgumentParser(description="Nettoie une partition brute SenMarket.")
    parseur.add_argument("--run-date", required=True, help="date de la partition, format AAAA-MM-JJ")
    args = parseur.parse_args(arguments)
    try:
        configurer_logging(args.run_date)
        resultat = nettoyer(lire_brut(args.run_date), args.run_date)
        ecrire_resultats(resultat, args.run_date)
    except (ErreurFichier, ValueError) as erreur:
        logger.error("%s", erreur)
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
