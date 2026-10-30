"""Chemins du projet SenMarket : le SEUL endroit où l'on construit un chemin.

Organisation des données :
    data/raw/date=AAAA-MM-JJ/        fichiers bruts générés
    data/processed/date=AAAA-MM-JJ/  tables nettoyées (CSV, Parquet, JSON Lines)
    data/rejected/date=AAAA-MM-JJ/   lignes en quarantaine et bilans

Aucune fonction de ce module ne crée de dossier : c'est à l'appelant de le faire,
au bon moment (après validation des entrées), pour ne jamais laisser de dossier
créé « à moitié » en cas d'échec.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

# src/senmarket/chemins.py → parents[0] = senmarket, [1] = src, [2] = racine du projet
RACINE = Path(__file__).resolve().parents[2]
load_dotenv(RACINE / ".env")

ZONES = ("raw", "processed", "rejected")


def valider_date(run_date: str) -> str:
    """Vérifie qu'une date est au format AAAA-MM-JJ et la renvoie telle quelle."""
    try:
        jour = date.fromisoformat(run_date)
    except (TypeError, ValueError):
        jour = None
    # fromisoformat accepte aussi « 20261029 » : on exige la forme exacte AAAA-MM-JJ
    if jour is None or jour.isoformat() != run_date:
        raise ValueError(
            f"Date invalide : {run_date!r}. Format attendu : AAAA-MM-JJ (ex. 2026-10-29)."
        )
    return run_date


def _verifier_zone(zone: str) -> None:
    if zone not in ZONES:
        raise ValueError(f"Zone inconnue : {zone!r}. Zones possibles : {', '.join(ZONES)}.")


def dossier_donnees() -> Path:
    """Dossier racine des données, lu dans SENMARKET_DATA_DIR (défaut : data/)."""
    chemin = Path(os.getenv("SENMARKET_DATA_DIR", "data")).expanduser()
    return chemin if chemin.is_absolute() else RACINE / chemin


def partition(zone: str, run_date: str) -> Path:
    """Chemin d'une partition, par exemple data/raw/date=2026-10-29 (sans la créer)."""
    _verifier_zone(zone)
    return dossier_donnees() / zone / f"date={valider_date(run_date)}"


def dossier_raw(run_date: str) -> Path:
    return partition("raw", run_date)


def dossier_processed(run_date: str) -> Path:
    return partition("processed", run_date)


def dossier_rejected(run_date: str) -> Path:
    return partition("rejected", run_date)


def lister_partitions(zone: str) -> list[str]:
    """Dates des partitions existantes d'une zone, triées (liste vide s'il n'y en a aucune)."""
    _verifier_zone(zone)
    base = dossier_donnees() / zone
    if not base.is_dir():
        return []
    return sorted(p.name.removeprefix("date=") for p in base.glob("date=*") if p.is_dir())


def dossier_logs() -> Path:
    return RACINE / "logs"


def dossier_figures() -> Path:
    return RACINE / "reports" / "figures"
