import pytest

from senmarket import chemins


def test_partition_raw(tmp_path, monkeypatch):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    attendu = tmp_path / "raw" / "date=2026-10-29"
    assert chemins.dossier_raw("2026-10-29") == attendu


def test_partition_ne_cree_aucun_dossier(tmp_path, monkeypatch):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    chemins.dossier_processed("2026-10-29")
    assert list(tmp_path.iterdir()) == []


def test_dossier_relatif_resolu_depuis_la_racine(monkeypatch):
    monkeypatch.setenv("SENMARKET_DATA_DIR", "data")
    assert chemins.dossier_donnees() == chemins.RACINE / "data"


@pytest.mark.parametrize("mauvaise_date", ["2026-13-01", "29/10/2026", "20261029", "", "demain"])
def test_date_invalide_leve_une_erreur_claire(mauvaise_date):
    with pytest.raises(ValueError, match="AAAA-MM-JJ"):
        chemins.dossier_raw(mauvaise_date)


def test_zone_inconnue(tmp_path, monkeypatch):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="Zone inconnue"):
        chemins.partition("brouillon", "2026-10-29")


def test_lister_partitions(tmp_path, monkeypatch):
    monkeypatch.setenv("SENMARKET_DATA_DIR", str(tmp_path))
    assert chemins.lister_partitions("raw") == []
    for d in ["2026-11-02", "2026-10-29"]:
        chemins.dossier_raw(d).mkdir(parents=True)
    assert chemins.lister_partitions("raw") == ["2026-10-29", "2026-11-02"]
