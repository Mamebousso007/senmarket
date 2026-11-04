"""Export JSON Lines : un objet JSON par ligne (format adapté à l'ingestion en flux)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def exporter_jsonl(df: pd.DataFrame, chemin: Path) -> Path:
    """Écrit une table en JSON Lines (UTF-8, accents lisibles). Les dates doivent déjà être du texte."""
    df.to_json(chemin, orient="records", lines=True, force_ascii=False)
    return chemin
