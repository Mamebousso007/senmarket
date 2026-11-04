# SenMarket — Chapitre 6 : Visualisation des données

## 1. Objectif du chapitre

Ce chapitre porte sur la visualisation exploratoire des données avec **Matplotlib** et **Seaborn**.

L’objectif est de transformer les données analysées dans les chapitres précédents en graphiques permettant de mieux comprendre l’activité commerciale de SenMarket : les montants des ventes, les différences entre les villes, les produits les plus vendus, les indicateurs clients et l’évolution du chiffre d’affaires.

Les graphiques ont été générés à partir des données traitées du **29 octobre 2026**, situées dans :

```text
data/processed/date=2026-10-29/
```

## 2. Les graphiques réalisés

### 2.1. Distribution des montants des ventes

**Fichier :** `01_distribution_montants.png`

**Objectif :** observer la répartition des montants des lignes de vente.

Ce graphique permet notamment de :
- Repérer les montants les plus fréquents.
- Observer si les montants sont concentrés dans une certaine plage.
- Détecter une éventuelle asymétrie de la distribution.
- Identifier des montants particulièrement élevés.

**Interprétation métier :**

Cette visualisation aide à comprendre les habitudes d’achat en matière de montant. Elle peut également mettre en évidence des ventes atypiques qui méritent une analyse complémentaire.

### 2.2. Dispersion des montants par ville

**Fichier :** `02_montants_par_ville.png`

**Objectif :** comparer la distribution des montants des ventes entre les principales villes.

Le diagramme en boîte (*boxplot*) permet de visualiser :
- La médiane des montants.
- La dispersion des valeurs.
- L’étendue de la partie centrale des données.
- Les valeurs potentiellement atypiques.

**Interprétation métier :**

Cette visualisation permet de comparer les montants des ventes selon les villes et de repérer celles où les montants sont particulièrement dispersés.

Une valeur atypique ne signifie pas nécessairement qu’il y a une erreur : elle peut correspondre à une vente exceptionnellement importante.

### 2.3. Les dix produits les plus vendus en quantité

**Fichier :** `03_top10_produits_quantite.png`

**Objectif :** identifier les dix produits présentant les quantités vendues les plus élevées.

Ce graphique en barres horizontales facilite la comparaison des produits.

**Interprétation métier :**

Cette visualisation peut aider SenMarket à :
- Identifier les produits les plus demandés en volume.
- Orienter les décisions de réapprovisionnement.
- Repérer les produits qui méritent un suivi commercial particulier.

**Point important :** un produit vendu en grande quantité n’est pas nécessairement celui qui génère le plus de chiffre d’affaires. Il faut distinguer le volume des ventes du montant des ventes.

### 2.4. Heatmap des indicateurs clients

**Fichier :** `04_heatmap_indicateurs_clients.png`

**Objectif :** visualiser plusieurs indicateurs associés aux clients dans une même représentation graphique.

Les indicateurs étudiés comprennent :
- Le nombre de commandes.
- Le chiffre d’affaires associé au client.
- Le panier moyen.
- La note moyenne des avis, lorsqu’elle est disponible.
- L’ancienneté du client en jours.

Une *heatmap* représente les valeurs sous forme de cellules colorées, ce qui facilite l’identification de différences entre les indicateurs ou les clients.

**Interprétation métier :**

Cette visualisation peut contribuer à repérer les clients qui commandent fréquemment, ceux qui génèrent un chiffre d’affaires élevé ou ceux qui présentent d’autres caractéristiques intéressantes pour l’analyse commerciale.

**Point de vigilance :** ces indicateurs utilisent des unités et des échelles différentes. Leur comparaison visuelle doit donc être prudente. Une association entre deux indicateurs ne prouve pas qu’un indicateur provoque l’autre.

### 2.5. Évolution mensuelle du chiffre d’affaires

**Fichier :** `05_evolution_mensuelle_ca.png`

**Objectif :** observer l’évolution du chiffre d’affaires au fil des mois.

Le graphique en courbes permet de visualiser les variations du chiffre d’affaires mensuel.

**Interprétation métier :**

Cette visualisation peut permettre de :
- Repérer les périodes de hausse ou de baisse.
- Identifier les mois présentant des variations importantes.
- Étudier l’évolution de l’activité commerciale.
- Préparer des analyses complémentaires sur la saisonnalité.

Il faut toutefois tenir compte de la période disponible et vérifier que les derniers mois ne sont pas incomplets avant de tirer des conclusions.

---

## 3. Bibliothèques Python utilisées

### 3.1. Pandas

Pandas sert à préparer les données avant leur représentation graphique.

Fonctions et méthodes utilisées dans cette étape :
- `groupby()` : regrouper les données selon un critère.
- `sum()` : calculer une somme.
- `mean()` : calculer une moyenne.
- `sort_values()` : trier les résultats.
- `head()` : sélectionner les premières lignes.
- `merge()` : combiner plusieurs tableaux.
- `to_datetime()` : convertir une colonne en dates.

### 3.2. Matplotlib

Matplotlib permet de créer et de personnaliser les graphiques.

Exemples de fonctionnalités :
- `plt.figure()` : créer une figure.
- `plt.title()` : ajouter un titre.
- `plt.xlabel()` : nommer l’axe horizontal.
- `plt.ylabel()` : nommer l’axe vertical.
- `plt.tight_layout()` : ajuster la disposition des éléments.
- `plt.savefig()` : enregistrer le graphique dans un fichier.
- `plt.show()` : afficher le graphique.

### 3.3. Seaborn

Seaborn facilite la création de visualisations statistiques à partir de données structurées.

Les types de graphiques utilisés comprennent :
- `histplot()` : histogramme.
- `boxplot()` : diagramme en boîte.
- `barplot()` : graphique en barres.
- `heatmap()` : carte de chaleur.

Seaborn s’appuie sur Matplotlib et permet de personnaliser facilement l’apparence des graphiques.

### 3.4. pathlib

Le module `pathlib` permet de manipuler les chemins de fichiers et de dossiers.

Exemple :

```python
from pathlib import Path

DOSSIER_FIGURES = Path("../reports/figures")
DOSSIER_FIGURES.mkdir(parents=True, exist_ok=True)
```

Cette instruction crée le dossier de sortie s’il n’existe pas déjà.

---

## 4. Organisation des livrables

Les graphiques sont enregistrés dans le dossier suivant :

```text
reports/
└── figures/
    ├── 01_distribution_montants.png
    ├── 02_montants_par_ville.png
    ├── 03_top10_produits_quantite.png
    ├── 04_heatmap_indicateurs_clients.png
    └── 05_evolution_mensuelle_ca.png
```

Le notebook associé est :

```text
notebooks/
└── 03_visualisation.ipynb
```

Le notebook contient le code Python utilisé pour préparer les données, générer les graphiques et les enregistrer.

---

## 5. Bonnes pratiques de visualisation

Pour produire des graphiques utiles et professionnels, il est important de respecter les bonnes pratiques suivantes :

1. **Choisir un graphique adapté à la question.** Un histogramme sert à étudier une distribution, tandis qu’une courbe convient mieux à l’évolution d’une mesure dans le temps.
2. **Ajouter un titre explicite.** Le lecteur doit comprendre rapidement ce qui est représenté.
3. **Nommer les axes.** Les unités doivent être indiquées lorsque cela est pertinent, notamment pour les montants en FCFA.
4. **Vérifier la lisibilité.** Les libellés ne doivent pas se chevaucher et les textes doivent rester suffisamment grands.
5. **Éviter les conclusions hâtives.** Un graphique permet d’observer des tendances, mais ne suffit pas toujours à en expliquer les causes.
6. **Enregistrer les figures.** Les fichiers PNG peuvent être intégrés à un rapport, à une présentation ou à une documentation technique.
7. **Vérifier les données utilisées.** Une erreur dans les regroupements ou les calculs peut conduire à un graphique visuellement correct, mais trompeur.

---

## 6. Bilan du chapitre

Le chapitre 6 a permis de mettre en pratique les bibliothèques Pandas, Matplotlib et Seaborn pour explorer et représenter les données commerciales de SenMarket.

Les cinq graphiques ont été générés sans erreur :

- Distribution des montants des ventes.
- Dispersion des montants par ville.
- Dix produits les plus vendus en quantité.
- Heatmap des indicateurs clients.
- Évolution mensuelle du chiffre d’affaires.

Les images sont enregistrées dans `reports/figures/` et le code correspondant se trouve dans `notebooks/03_visualisation.ipynb`.

**À retenir :** la visualisation ne consiste pas seulement à créer des graphiques. Elle permet de rendre les données compréhensibles, de formuler des observations et d’aider à orienter les décisions métier.

Pour compléter ce chapitre, il reste utile d’examiner chaque graphique et de rédiger quelques observations factuelles fondées sur ce qu’il montre réellement.
