# Chapitre 5 --- Analyse des données de SenMarket

## 1. Objectif

Ce chapitre utilise Pandas pour analyser les ventes, les produits, la
navigation, la rétention des clients et les paiements de SenMarket.

## 2. Données utilisées

Dossier source : `data/processed/date=2026-10-29/`

  Fichier                 Utilisation
  ----------------------- -----------------------------------------
  `lignes_commande.csv`   Quantités et montants des lignes
  `commandes.csv`         Dates, clients et statuts des commandes
  `clients.csv`           Villes et régions
  `produits.csv`          Informations sur les produits
  `navigation.csv`        Sessions et événements de navigation
  `paiements.csv`         Montants et statuts des paiements

Volumes chargés : **9 608 lignes de commande**, **3 920 commandes** et
**3 333 clients**.

## 3. Analyses réalisées

### 3.1 Chiffre d'affaires par ville et par région

Les tables des lignes de commande, commandes et clients sont reliées
avec `merge()` à partir de `commande_id` puis de `client_id`. Le chiffre
d'affaires est calculé en regroupant les lignes avec `groupby()` et en
additionnant `montant_xof`.

Les villes ou régions manquantes doivent être identifiées séparément,
par exemple sous le libellé **« Inconnue »**. Ce libellé n'est pas une
ville réelle.

**Contrôle recommandé :** la somme des chiffres d'affaires par ville (y
compris « Inconnue ») doit correspondre au chiffre d'affaires total.
Faire le même contrôle pour les régions.

### 3.2 Top 10 des produits

Deux classements sont calculés : - par quantité : somme de `quantite`
par produit ; - par chiffre d'affaires : somme de `montant_xof` par
produit.

Les classements peuvent différer : un produit peu cher peut être vendu
en grande quantité, alors qu'un produit coûteux peut générer un CA élevé
avec moins d'unités vendues.

    Rang Produit                              CA (XOF)
  ------ ------------------------------- -------------
       1 Climatiseur 12 000 BTU            159 012 035
       2 Téléviseur LED 43 pouces          124 246 518
       3 Ordinateur portable 15 pouces      58 831 205
       4 Smartphone Itel A70                47 674 600
       5 Bazin riche 5 m                    47 440 096
       6 Mixeur blender                     38 191 091
       7 Imprimante multifonction           34 343 416
       8 Cuisinière 4 feux                  26 970 491
       9 iPhone 13 reconditionné            24 607 761
      10 Réfrigérateur 180 L                23 500 686

Le climatiseur 12 000 BTU est premier avec **159 012 035 XOF**, suivi du
téléviseur LED 43 pouces avec **124 246 518 XOF**.

### 3.3 Panier moyen

Le montant de chaque commande est calculé en additionnant ses lignes,
puis le panier moyen est la moyenne des montants par commande.

-   Commandes contenant des lignes : **3 904**
-   Panier moyen : **189 486 XOF**
-   Montant moyen par ligne : **76 993 XOF**

Le panier moyen est supérieur au montant moyen par ligne car une
commande peut contenir plusieurs lignes de produits.

Le jeu de données comprend 3 920 commandes et 3 904 commandes avec des
lignes. Il faut donc examiner les **16 commandes sans ligne
correspondante**.

### 3.4 Conversion des sessions

Une session est considérée comme ayant atteint le début du paiement si
elle contient au moins un événement `debut_paiement`. Chaque session est
comptée une seule fois.

Formule : `sessions avec debut_paiement / sessions totales × 100`

-   Sessions distinctes : **8 000**
-   Sessions avec `debut_paiement` : **1 253**
-   Taux de conversion vers le début du paiement : **15,66 %**

Cela signifie qu'environ 15,66 % des sessions ont atteint cette étape.
Ce taux ne mesure pas les paiements réussis. Compter séparément les
sessions avec vue produit, ajout au panier et début de paiement ne forme
pas automatiquement un entonnoir strict : il faut vérifier l'ordre
chronologique des événements.

### 3.5 Cohortes et rétention

La cohorte d'un client est définie par le mois de sa première commande.
Les commandes sont regroupées selon le mois de cohorte et le nombre de
mois écoulés depuis la première commande.

Formule :
`clients de la cohorte ayant commandé pendant le mois étudié / clients de la cohorte au mois 0 × 100`

Le mois 0 correspond au mois de première commande et vaut donc **100
%**.

Exemples : - Cohorte de novembre 2025 : 176 clients au mois 0 et 37 au
mois 1, soit **21,0 %** de rétention au mois 1. - Cohorte de septembre
2026 : 152 clients au mois 0 et 41 au mois 1, soit environ **27,0 %**. -
Cohorte d'octobre 2026 : 165 clients au mois 0 ; le mois suivant n'est
pas encore couvert par les données présentées.

**Attention :** les périodes futures ou non observées ne doivent pas
être interprétées comme une rétention réelle de 0 %. Il faut les laisser
manquantes (valeur `NaN`/cellule vide), plutôt que de les remplir avec
zéro. Un zéro réel signifie qu'aucun client de la cohorte n'a commandé
pendant une période effectivement observée.

La rétention indique qu'un client a commandé pendant un mois donné ;
elle ne signifie pas qu'il commande nécessairement chaque mois.

### 3.6 Bonus : commandes et paiements réussis

-   CA des lignes de commande : **739 752 225 XOF**
-   Montant des paiements réussis : **669 168 696 XOF**
-   Écart arithmétique : **70 583 529 XOF**
-   Commandes sans paiement réussi identifié : **486**

Les deux montants ne sont pas nécessairement directement comparables :
il peut y avoir des commandes non payées, des paiements partiels ou
plusieurs paiements par commande. Il faut vérifier les valeurs réelles
de `statut_paiement` et s'assurer que le statut filtré correspond bien à
la convention des données. Il faut aussi contrôler les paiements
multiples ou partiels avant d'assimiler la somme des paiements réussis
au CA encaissé.

## 4. Fonctions Pandas utilisées

  Fonction              Rôle
  --------------------- ---------------------------------------
  `pd.read_csv()`       Charger un CSV
  `merge()`             Relier des tables
  `groupby()`           Regrouper des lignes
  `sum()`               Calculer une somme
  `agg()`               Appliquer des agrégations
  `sort_values()`       Trier
  `head(10)`            Garder les dix premiers résultats
  `nunique()`           Compter les valeurs distinctes
  `pd.to_datetime()`    Convertir des dates
  `dt.to_period("M")`   Créer une période mensuelle
  `unstack()`           Transformer une dimension en colonnes
  `div()`               Calculer les taux de rétention

## 5. Contrôles à finaliser

-   [ ] Vérifier que le CA par ville correspond au CA total, y compris «
    Inconnue ».
-   [ ] Vérifier que le CA par région correspond au CA total.
-   [ ] Comparer le Top 10 par quantité au Top 10 par CA.
-   [ ] Examiner les 16 commandes sans lignes.
-   [ ] Vérifier les événements de navigation et interpréter le taux
    comme une conversion vers le début du paiement.
-   [ ] Distinguer les périodes de rétention non observées des zéros
    réels.
-   [ ] Vérifier les statuts de paiement et les paiements multiples ou
    partiels.

## 6. Conclusion

Ce chapitre met en pratique le chargement de données, les jointures, les
regroupements, les agrégations et l'analyse temporelle avec Pandas. Les
principaux résultats sont un panier moyen de **189 486 XOF**, un taux de
sessions atteignant le début du paiement de **15,66 %**, un CA des
lignes de commande de **739 752 225 XOF** et un montant de paiements
réussis de **669 168 696 XOF**.

Ces résultats doivent être accompagnés des contrôles de cohérence et des
limites d'interprétation ci-dessus. L'objectif est de pouvoir expliquer
non seulement les valeurs calculées, mais aussi leur signification et
leurs limites.
