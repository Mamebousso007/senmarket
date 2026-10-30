"""Configuration du logging : console + fichier logs/pipeline_AAAA-MM-JJ.log.

Format : AAAA-MM-JJ HH:MM:SS NIVEAU module: message

Dans chaque module :
    import logging
    logger = logging.getLogger(__name__)
    logger.info("10000 lignes générées")

Au démarrage du pipeline (une seule fois) :
    from senmarket.journal import configurer_logging
    configurer_logging("2026-10-29")
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from senmarket.chemins import dossier_logs, valider_date

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
FORMAT_DATE = "%Y-%m-%d %H:%M:%S"
NIVEAUX = ("DEBUG", "INFO", "WARNING", "ERROR")


def configurer_logging(run_date: str, niveau: str | None = None) -> Path:
    """Configure la journalisation et renvoie le chemin du fichier de log.

    Le niveau vient du paramètre, sinon de SENMARKET_LOG_LEVEL, sinon INFO.
    On peut rappeler la fonction (dans un notebook par exemple) sans dupliquer les messages.
    """
    run_date = valider_date(run_date)
    niveau = (niveau or os.getenv("SENMARKET_LOG_LEVEL", "INFO")).upper()
    if niveau not in NIVEAUX:
        raise ValueError(
            f"Niveau de log invalide : {niveau!r}. Niveaux possibles : {', '.join(NIVEAUX)}."
        )

    dossier = dossier_logs()
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / f"pipeline_{run_date}.log"

    racine = logging.getLogger()
    for handler in list(racine.handlers):  # évite les doublons si on reconfigure
        racine.removeHandler(handler)
        handler.close()

    formateur = logging.Formatter(FORMAT, datefmt=FORMAT_DATE)
    for handler in (logging.StreamHandler(), logging.FileHandler(fichier, encoding="utf-8")):
        handler.setFormatter(formateur)
        racine.addHandler(handler)
    racine.setLevel(niveau)

    return fichier
