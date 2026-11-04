# SenMarket — Module 0 : Python, données et environnement de travail

Fil rouge du programme **Data Engineering, Big Data & DataOps** (Orange Digital Center).

SenMarket est une marketplace sénégalaise **fictive**. Ce projet fabrique ses données, les abîme volontairement, puis les nettoie, les analyse et les visualise. Les données sont **synthétiques** : elles ne représentent ni des transactions réelles ni des statistiques officielles. Tous les montants sont en francs CFA (XOF), en entiers.

Ce dépôt est la première brique du parcours : les modules suivants (bases de données, Spark, ingestion, dbt) s'appuient sur les données produites ici.

---

## 1. Installation (depuis un dépôt vierge)

**Prérequis** : Python 3.12 (3.11 accepté, 3.14 déconseillé), Git, un terminal Linux, WSL ou macOS.

```bash
git clone https://github.com/Mamebousso007/senmarket.git ~/senmarket
cd ~/senmarket
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env
```

Le fichier `.env` contient la configuration locale (dossier des données, graine, niveau de journalisation). Il n'est **jamais** versionné : seul `.env.example` l'est.

## 2. Vérifier l'installation

```bash
python -c "import senmarket; print(senmarket.__version__)"
python -m pytest -q
```

Résultat attendu : `0.1.0`, puis **100 passed**.

---

## 3. Utilisation

### 3.1 Générer les données brutes

```bash
# Données propres (sans défaut)
python -m senmarket.generateur --run-date 2026-10-29

# Données avec les 8 défauts du module (doublons, montants en texte, dates futures…)
python -m senmarket.generateur --run-date 2026-10-29 --defauts tous

# Partition « volume » (200 000 lignes de commande)
python -m senmarket.generateur --run-date 2026-11-02 --rows 200000 --defauts tous
```

| Option | Rôle | Défaut |
|---|---|---|
| `--run-date AAAA-MM-JJ` | date d'exécution ; détermine la graine et la partition | obligatoire |
| `--rows N` | nombre de lignes de commande | 10 000 |
| `--jours N` | nombre de jours couverts par les commandes | 365 |
| `--defauts ...` | défauts à injecter (`tous`, ou une liste de noms) | aucun |
| `--taux nom=valeur` | taux d'un défaut, par exemple `outlier=0.05` | taux du module |
| `--ecraser` | remplace une partition existante | non |

Sortie dans `data/raw/date=AAAA-MM-JJ/` : les 8 tables en CSV, `bilan_generation.csv` (les défauts injectés) et `senmarket.log` (journal d'ingestion simulé).

### 3.2 Nettoyer

```bash
python -m senmarket.nettoyage --run-date 2026-10-29
```

Sorties :
- `data/processed/date=AAAA-MM-JJ/` : les 8 tables propres en CSV, Parquet et JSON Lines (`json/`) ;
- `data/rejected/date=AAAA-MM-JJ/` : les lignes en quarantaine avec leur motif (`<table>_rejetes.csv`), `bilan_nettoyage.csv`, `motifs_rejet.csv` et `corrections.csv`.

Règle du nettoyage : on **corrige** ce qui est réparable (montant en texte, montant manquant recalculé, encodage), on **étiquette** ce qui manque (« Inconnue »), et on met en **quarantaine** ce qui est irréparable. Une ligne rejetée n'est jamais effacée. Pour chaque table : brut = accepté + rejeté.

### 3.3 Prouver la reproductibilité

Deux exécutions avec la même date produisent exactement les mêmes fichiers :

```bash
cd data/raw/date=2026-10-29 && sha256sum *.csv senmarket.log > /tmp/h1.txt && cd ~/senmarket
python -m senmarket.generateur --run-date 2026-10-29 --defauts tous --ecraser
cd data/raw/date=2026-10-29 && sha256sum *.csv senmarket.log > /tmp/h2.txt && cd ~/senmarket
diff /tmp/h1.txt /tmp/h2.txt && echo "identique"
```

### 3.4 Les notebooks

```bash
jupyter lab
```

| Notebook | Contenu | Données nécessaires |
|---|---|---|
| `notebooks/01_nettoyage.ipynb` | comparaison des formats CSV, JSON, JSON Lines, Parquet | partition volume brute (`2026-11-02`) |
| `notebooks/02_analyse.ipynb` | CA par ville et région, top produits, panier moyen, conversion, cohortes | partition nettoyée (`2026-10-29`) |
| `notebooks/03_visualisation.ipynb` | 5 graphiques exportés dans `reports/figures/` | partition nettoyée (`2026-10-29`) |

Ordre conseillé : générer, nettoyer, puis ouvrir les notebooks.

---

## 4. Organisation du dépôt

```
senmarket/
├── src/senmarket/
│   ├── chemins.py          chemins des partitions (seul endroit qui construit un chemin)
│   ├── journal.py          configuration du logging (console + logs/)
│   ├── referentiels.py     villes, noms sénégalais, produits, proportions
│   ├── generateur.py       génération des 8 tables et écriture des CSV bruts
│   ├── defauts.py          injection contrôlée des défauts et bilan
│   ├── nettoyage.py        correction, validation, quarantaine en cascade
│   └── export.py           export JSON Lines
├── tests/                  100 tests pytest (chemins, journal, générateur, défauts, nettoyage)
├── notebooks/              01_nettoyage, 02_analyse, 03_visualisation (+ apprentissage/)
├── reports/figures/        les 5 graphiques PNG
├── docs/                   contrat de données, mesures, analyse, visualisation
├── data/                   créé automatiquement, ignoré par Git
└── logs/                   journaux d'exécution, ignorés par Git
```

## 5. Documentation

| Document | Contenu |
|---|---|
| [`docs/CONTRAT_DONNEES.md`](docs/CONTRAT_DONNEES.md) | les 8 tables : colonnes, types, clés, relations, règles métier |
| [`docs/MESURES.md`](docs/MESURES.md) | machine, temps de génération, reproductibilité, comparaison des formats |
| [`docs/ANALYSE.md`](docs/ANALYSE.md) | résultats et limites des 5 questions métier |
| [`docs/VISUALISATION.md`](docs/VISUALISATION.md) | les 5 graphiques et leur interprétation |

---

## 6. État d'avancement

| Chapitre | Ticket | État |
|---|---|---|
| 0 — Poser le chantier | SM-001 | ✅ |
| 1 — Contrat de données | SM-002 | ✅ |
| 2 — Générer le dataset sale | SM-003 | ✅ |
| 3 — Comparer les formats | SM-004 | ✅ |
| 4 — Nettoyer | SM-005 | ✅ code et tests ; notebook de justification à compléter |
| 5 — Analyser | SM-006 | ✅ notebook ; `analyse.py` à écrire |
| 6 — Visualiser | SM-007 | ✅ notebook et graphiques ; `visualisation.py` à écrire |
| 7 — Shell | SM-008 | à faire |
| 8 — Orchestrer | SM-009 | à faire (`scripts/run_pipeline.py`, `DECISIONS.md`) |

---

## 7. Dépannage

- **`ModuleNotFoundError: No module named 'senmarket'`** : l'environnement virtuel n'est pas activé (`source .venv/bin/activate`), ou `pip install -e .` n'a pas été lancé.
- **« La partition brute … existe déjà »** : relancer avec `--ecraser` pour la remplacer.
- **« La partition brute … n'existe pas »** (au nettoyage) : générer d'abord la partition avec `senmarket.generateur`.
- **`pip install` échoue** : vérifier `python --version`. En 3.14, certains paquets n'ont pas encore de version précompilée : recréer le venv en 3.12.
