"""Injection contrôlée de défauts dans la « vérité ».

Principe : on part des 8 tables propres, on les COPIE, puis on abîme la copie en comptant
chaque défaut injecté. Le bilan obtenu est la référence que le nettoyage (chapitre 4)
devra retrouver.

Défauts « de ligne » (activés par --defauts nom1 nom2 ... ou --defauts tous) :
    doublon_ligne, valeurs_manquantes, date_future, montant_texte, outlier,
    quantite_negative, encodage_nom, paiement_orphelin
Défauts « de fichier » (jamais inclus dans « tous », pour l'épreuve du chapitre 4) :
    encodage_latin1, colonne_manquante
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# nom du défaut : (taux par défaut, table touchée, colonne(s) touchée(s))
CATALOGUE = {
    "doublon_ligne":      (0.05, "lignes_commande", "toutes"),
    "valeurs_manquantes": (0.08, "clients + lignes_commande", "nom_client, email, ville, montant_xof"),
    "date_future":        (0.02, "commandes", "date_commande"),
    "montant_texte":      (0.03, "lignes_commande", "montant_xof"),
    "outlier":            (0.01, "lignes_commande", "prix_unitaire_xof"),
    "quantite_negative":  (0.01, "lignes_commande", "quantite"),
    "encodage_nom":       (0.02, "clients", "nom_client"),
    "paiement_orphelin":  (0.01, "paiements", "commande_id"),
    "encodage_latin1":    (None, "clients", "fichier entier"),
    "colonne_manquante":  (None, "lignes_commande", "quantite"),
}
DEFAUTS_DE_LIGNE = [nom for nom, (taux, _, _) in CATALOGUE.items() if taux is not None]
DEFAUTS_DE_FICHIER = [nom for nom, (taux, _, _) in CATALOGUE.items() if taux is None]

PRIX_OUTLIER = 99_999_999
FORMATS_MONTANT = [  # (séparateur des milliers, suffixe) → « 45 000 FCFA », « 45000 F CFA », « 45.000 XOF »
    (" ", " FCFA"),
    ("", " F CFA"),
    (".", " XOF"),
]


def lire_options(defauts: list[str] | None, taux: list[str] | None) -> tuple[list[str], dict[str, float]]:
    """Transforme les options de la ligne de commande en (liste de défauts, taux par défaut).

    defauts : ["tous"] ou une liste de noms ; taux : ["outlier=0.02", ...].
    """
    actifs = []
    for nom in defauts or []:
        if nom == "tous":
            actifs += DEFAUTS_DE_LIGNE
        elif nom in CATALOGUE:
            actifs.append(nom)
        else:
            raise ValueError(f"Défaut inconnu : {nom!r}. Défauts possibles : tous, {', '.join(CATALOGUE)}.")
    actifs = list(dict.fromkeys(actifs))          # sans doublon, dans l'ordre

    taux_final = {nom: t for nom, (t, _, _) in CATALOGUE.items() if t is not None}
    for texte in taux or []:
        nom, _, valeur = texte.partition("=")
        if nom not in taux_final:
            raise ValueError(f"--taux : défaut inconnu ou sans taux : {nom!r}.")
        try:
            taux_final[nom] = float(valeur)
        except ValueError:
            raise ValueError(f"--taux : valeur illisible pour {nom} : {valeur!r} (exemple : outlier=0.02).") from None
        if not 0 <= taux_final[nom] < 1:
            raise ValueError(f"--taux : {nom} doit être entre 0 et 1 (reçu : {valeur}).")
    return actifs, taux_final


def _format_montant(valeur: int, separateur: str, suffixe: str) -> str:
    return f"{valeur:,}".replace(",", separateur) + suffixe


def injecter_defauts(verite: dict[str, pd.DataFrame], actifs: list[str], taux: dict[str, float],
                     run_date: str, graine: int) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Renvoie (tables abîmées, bilan). La vérité reçue n'est jamais modifiée."""
    rng = np.random.default_rng([graine, 1])     # générateur distinct de celui de la vérité
    tables = {nom: df.copy() for nom, df in verite.items()}
    bilan = []

    def actif(nom):
        return nom in actifs

    def combien(nom, n_total):
        return round(taux[nom] * n_total) if actif(nom) else 0

    def noter(defaut, table, colonne, lignes, base):
        bilan.append({"defaut": defaut, "table": table, "colonne": colonne,
                      "lignes_injectees": int(lignes), "lignes_table_verite": int(base),
                      "taux_demande": taux.get(defaut, 0.0) if actif(defaut) else 0.0})

    # --- clients : valeurs manquantes et encodage abîmé -----------------------
    clients = tables["clients"]
    nb_c = len(clients)
    for col in ["nom_client", "email", "ville"]:
        n = combien("valeurs_manquantes", nb_c)
        clients.loc[rng.choice(nb_c, size=n, replace=False), col] = np.nan
        noter("valeurs_manquantes", "clients", col, n, nb_c)

    # Encodage : uniquement des noms qui ont des accents (sinon le défaut serait invisible)
    candidats = np.flatnonzero(clients["nom_client"].notna()
                               & clients["nom_client"].str.contains(r"[^\x00-\x7F]", na=False).to_numpy())
    n = min(combien("encodage_nom", nb_c), len(candidats))
    choisis = rng.choice(candidats, size=n, replace=False)
    clients.loc[choisis, "nom_client"] = [nom.encode("utf-8").decode("latin-1")
                                          for nom in clients.loc[choisis, "nom_client"]]
    noter("encodage_nom", "clients", "nom_client", n, nb_c)

    # --- commandes : dates dans le futur --------------------------------------
    commandes = tables["commandes"]
    n = combien("date_future", len(commandes))
    choisis = rng.choice(len(commandes), size=n, replace=False)
    commandes.loc[choisis, "date_commande"] = (pd.Timestamp(run_date)
                                               + pd.to_timedelta(rng.integers(1, 366, size=n), unit="D"))
    noter("date_future", "commandes", "date_commande", n, len(commandes))

    # --- lignes de commande : 4 défauts sur des lignes DIFFÉRENTES --------------
    lignes = tables["lignes_commande"]
    nb_l = len(lignes)
    n_manquant = combien("valeurs_manquantes", nb_l)
    n_texte = combien("montant_texte", nb_l)
    n_outlier = combien("outlier", nb_l)
    n_negatif = combien("quantite_negative", nb_l)
    ordre = rng.permutation(nb_l)
    bornes = np.cumsum([0, n_manquant, n_texte, n_outlier, n_negatif])
    pos_manquant, pos_texte, pos_outlier, pos_negatif = (ordre[bornes[i]:bornes[i + 1]] for i in range(4))

    # Outlier et quantité négative : le montant est recalculé pour rester cohérent
    lignes.loc[pos_outlier, "prix_unitaire_xof"] = PRIX_OUTLIER
    lignes.loc[pos_negatif, "quantite"] = rng.choice([0, -1, -2, -3], size=len(pos_negatif))
    touchees = np.concatenate([pos_outlier, pos_negatif])
    lignes.loc[touchees, "montant_xof"] = (lignes.loc[touchees, "quantite"]
                                           * lignes.loc[touchees, "prix_unitaire_xof"])

    # Montant : la colonne devient « object » pour accepter du texte et des vides
    # (pandas 3 refuse de mettre du texte dans une colonne d'entiers)
    if n_texte or n_manquant:
        montant = lignes["montant_xof"].astype(object)
        formats = rng.integers(0, len(FORMATS_MONTANT), size=len(pos_texte))
        montant.iloc[pos_texte] = [_format_montant(int(v), *FORMATS_MONTANT[f])
                                   for v, f in zip(montant.iloc[pos_texte], formats)]
        montant.iloc[pos_manquant] = np.nan
        lignes["montant_xof"] = montant

    noter("valeurs_manquantes", "lignes_commande", "montant_xof", n_manquant, nb_l)
    noter("montant_texte", "lignes_commande", "montant_xof", n_texte, nb_l)
    noter("outlier", "lignes_commande", "prix_unitaire_xof", n_outlier, nb_l)
    noter("quantite_negative", "lignes_commande", "quantite", n_negatif, nb_l)

    # Doublons en DERNIER : une copie reprend l'état final de la ligne copiée
    n = combien("doublon_ligne", nb_l)
    copies = lignes.iloc[np.sort(rng.choice(nb_l, size=n, replace=False))]
    tables["lignes_commande"] = pd.concat([lignes, copies], ignore_index=True)
    noter("doublon_ligne", "lignes_commande", "toutes", n, nb_l)

    # --- paiements : paiements orphelins (ajoutés, la vérité n'est pas modifiée) ---
    paiements = tables["paiements"]
    n = combien("paiement_orphelin", len(paiements))
    if n:
        modeles = paiements.iloc[rng.choice(len(paiements), size=n, replace=False)].copy()
        modeles["paiement_id"] = ["PAI" + str(len(paiements) + i + 1).zfill(7) for i in range(n)]
        modeles["commande_id"] = ["CMD9" + str(x).zfill(6) for x in rng.integers(0, 1_000_000, size=n)]
        tables["paiements"] = pd.concat([paiements, modeles], ignore_index=True)
    noter("paiement_orphelin", "paiements", "commande_id", n, len(paiements))

    # --- défauts de fichier : notés ici, appliqués au moment de l'écriture --------
    for nom in DEFAUTS_DE_FICHIER:
        _, table, colonne = CATALOGUE[nom]
        noter(nom, table, colonne, 1 if actif(nom) else 0, len(verite[table]))

    return tables, pd.DataFrame(bilan)
