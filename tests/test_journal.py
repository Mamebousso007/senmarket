import logging
import re

import pytest

from senmarket import journal


def test_format_du_fichier_de_log(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "dossier_logs", lambda: tmp_path)
    fichier = journal.configurer_logging("2026-10-29", niveau="INFO")

    logging.getLogger("senmarket.test").info("10000 lignes chargées")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert fichier.name == "pipeline_2026-10-29.log"
    ligne = fichier.read_text(encoding="utf-8").strip()
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO senmarket\.test: 10000 lignes chargées", ligne
    )


def test_reconfigurer_ne_duplique_pas_les_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "dossier_logs", lambda: tmp_path)
    journal.configurer_logging("2026-10-29")
    journal.configurer_logging("2026-10-29")
    assert len(logging.getLogger().handlers) == 2  # une console + un fichier


def test_niveau_invalide(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "dossier_logs", lambda: tmp_path)
    with pytest.raises(ValueError, match="Niveau de log invalide"):
        journal.configurer_logging("2026-10-29", niveau="BAVARD")
