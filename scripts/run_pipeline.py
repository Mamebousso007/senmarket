"""Pipeline SenMarket : une seule commande qui refait tout (Module 0, chapitre 8, ticket SM-009).

Étapes, dans l'ordre :
    1. génération      (seulement avec --generer)       → data/raw/date=AAAA-MM-JJ/
    2. nettoyage + export JSON Lines                    → data/processed/ et data/rejected/
    3. analyse         (si src/senmarket/analyse.py existe)
    4. graphiques      (si src/senmarket/visualisation.py existe)
    5. tests de qualité sur la partition produite (sauf avec --sans-tests)

Exemples :
    python scripts/run_pipeline.py --run-date 2026-10-29 --generer --defauts tous
    python scripts/run_pipeline.py --run-date 2026-11-02 --generer --rows 200000 --defauts tous --sans-tests
    python scripts/run_pipeline.py --run-date 2026-10-29          # renettoie une partition déjà générée

Code de retour : 0 si tout s'est bien passé, 1 sinon (avec un message qui dit quoi faire).
"""

from __future__ import annotations

import argparse
import importlib
import logging
import os
import subprocess
import sys
import time

from senmarket import generateur, nettoyage
from senmarket.chemins import RACINE, dossier_raw, valider_date
from senmarket.journal import configurer_logging

logger = logging.getLogger("senmarket.pipeline")


def lire_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    parseur = argparse.ArgumentParser(description="Pipeline SenMarket : génération → nettoyage → tests.")
    parseur.add_argument("--run-date", required=True, help="date de la partition, format AAAA-MM-JJ")
    parseur.add_argument("--generer", action="store_true", help="génère d'abord la partition brute")
    parseur.add_argument("--ecraser", action="store_true", help="remplace une partition brute existante")
    parseur.add_argument("--rows", type=int, default=10_000, help="nombre de lignes de commande")
    parseur.add_argument("--jours", type=int, default=365, help="nombre de jours couverts")
    parseur.add_argument("--defauts", nargs="*", default=[], help="défauts à injecter, ou « tous »")
    parseur.add_argument("--taux", nargs="*", default=[], help="taux d'un défaut, ex. outlier=0.02")
    parseur.add_argument("--sans-tests", action="store_true", help="ne lance pas les tests de qualité")
    return parseur.parse_args(arguments)


class ArretPipeline(Exception):
    """Arrêt volontaire du pipeline, avec un message qui dit quoi faire."""


def verifier_avant_de_commencer(args: argparse.Namespace) -> None:
    """Toutes les vérifications AVANT d'écrire quoi que ce soit (aucun dossier créé en cas d'arrêt)."""
    valider_date(args.run_date)
    brut = dossier_raw(args.run_date)
    if args.generer and brut.exists() and not args.ecraser:
        raise ArretPipeline(
            f"La partition brute {brut} existe déjà. Ajoute --ecraser pour la régénérer, "
            f"ou retire --generer pour seulement la renettoyer."
        )
    if not args.generer and not brut.exists():
        raise ArretPipeline(
            f"La partition brute {brut} n'existe pas. Pour la créer, relance avec --generer :\n"
            f"  python scripts/run_pipeline.py --run-date {args.run_date} --generer --defauts tous"
        )


def etape_generation(args: argparse.Namespace) -> None:
    options = ["--run-date", args.run_date, "--rows", str(args.rows), "--jours", str(args.jours)]
    if args.defauts:
        options += ["--defauts", *args.defauts]
    if args.taux:
        options += ["--taux", *args.taux]
    if args.ecraser:
        options.append("--ecraser")
    if generateur.main(options) != 0:
        raise ArretPipeline("La génération a échoué : lis le message d'erreur ci-dessus.")


def etape_nettoyage(args: argparse.Namespace) -> None:
    # nettoyage.main écrit aussi l'export JSON Lines dans processed/json/
    if nettoyage.main(["--run-date", args.run_date]) != 0:
        raise ArretPipeline("Le nettoyage a échoué : lis le message d'erreur ci-dessus.")


def etape_facultative(nom_module: str, run_date: str) -> None:
    """Lance senmarket.<nom_module>.produire(run_date) si le module existe déjà."""
    try:
        module = importlib.import_module(f"senmarket.{nom_module}")
    except ModuleNotFoundError as erreur:
        if erreur.name != f"senmarket.{nom_module}":
            raise                                    # une vraie dépendance manquante : on ne la cache pas
        logger.warning("Étape %s ignorée : src/senmarket/%s.py n'existe pas encore", nom_module, nom_module)
        return
    if not hasattr(module, "produire"):
        logger.warning("Étape %s ignorée : %s.py n'a pas encore de fonction produire(run_date)",
                       nom_module, nom_module)
        return
    module.produire(run_date)


def etape_tests(run_date: str) -> None:
    environnement = os.environ | {"SENMARKET_PARTITION": run_date}
    commande = [sys.executable, "-m", "pytest", "-q", "tests/test_qualite_donnees.py"]
    resultat = subprocess.run(commande, cwd=RACINE, env=environnement)
    if resultat.returncode != 0:
        raise ArretPipeline("Des tests de qualité échouent : lis le détail de pytest ci-dessus.")


def main(arguments: list[str] | None = None) -> int:
    args = lire_arguments(arguments)
    try:
        verifier_avant_de_commencer(args)
    except (ArretPipeline, ValueError) as erreur:   # rien n'a été écrit : pas même un fichier de log
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1

    configurer_logging(args.run_date)
    etapes = []
    if args.generer:
        etapes.append(("génération", lambda: etape_generation(args)))
    etapes += [
        ("nettoyage et export JSON Lines", lambda: etape_nettoyage(args)),
        ("analyse", lambda: etape_facultative("analyse", args.run_date)),
        ("graphiques", lambda: etape_facultative("visualisation", args.run_date)),
    ]
    if not args.sans_tests:
        etapes.append(("tests de qualité", lambda: etape_tests(args.run_date)))

    debut_total = time.perf_counter()
    for numero, (nom, etape) in enumerate(etapes, start=1):
        logger.info("Étape %d/%d : %s", numero, len(etapes), nom)
        debut = time.perf_counter()
        try:
            etape()
        except ArretPipeline as erreur:
            logger.error("Pipeline arrêté à l'étape « %s » : %s", nom, erreur)
            print(f"Erreur : {erreur}", file=sys.stderr)
            return 1
        logger.info("Étape %d/%d terminée en %.1f s", numero, len(etapes), time.perf_counter() - debut)

    logger.info("Pipeline terminé en %.1f s pour la partition %s",
                time.perf_counter() - debut_total, args.run_date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
