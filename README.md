# SenMarket — Module 0

Fil rouge du programme Data Engineering : génération, nettoyage, analyse et visualisation
des données d'une marketplace sénégalaise fictive.

## Installation (depuis un dépôt vierge)

Prérequis : Python 3.12 (3.11 accepté), Git, un terminal Linux / WSL / macOS.

```bash
git clone <url-du-depot> ~/senmarket
cd ~/senmarket
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env
```

## Vérifier l'installation

```bash
python -c "import senmarket; print(senmarket.__version__)"
python -m pytest -q
```

## Exécuter le pipeline

*(à compléter au chapitre 8)*
