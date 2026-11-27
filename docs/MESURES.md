# Mesures

Ce fichier documente ma machine et les mesures du module (chapitres 2 et 3).

## Machine (partie A3)

Sortie de :

```bash
python --version
which python
git --version
python -c "import numpy, pandas, pyarrow, faker, pytest; print('ok')"
nproc && free -h
```

```text
(colle ici la sortie)
```

## Génération (chapitre 2)

| Commande | Lignes | Temps | Remarque |
|---|---|---|---|
| | | | |

## Formats (chapitre 3)

| Format | Temps médian (5 mesures) | Taille | Type de date_commande |
|---|---|---|---|
| | | | |

## Module 1 — Partition volume (A5)

Pipeline complet --rows 200000 (génération + nettoyage) : 9,5 s.

## Module 1 — Contrôle de pré-vol (A4)

```text
Partition contrôlée : date=2026-10-29
clients              3333 lignes | clé primaire unique : True
vendeurs               20 lignes | clé primaire unique : True
produits               40 lignes | clé primaire unique : True
commandes            3920 lignes | clé primaire unique : True
lignes_commande      9608 lignes | clé primaire unique : True
paiements            3838 lignes | clé primaire unique : True
avis                  865 lignes | clé primaire unique : True
navigation          20103 lignes | clé primaire unique : True
commandes.client_id -> clients : 0 orphelin(s)
lignes_commande.commande_id -> commandes : 0 orphelin(s)
lignes_commande.produit_id -> produits : 0 orphelin(s)
paiements.commande_id -> commandes : 0 orphelin(s)
avis.produit_id -> produits : 0 orphelin(s)
Paiement égal à la somme des lignes : 94.5%
produits.stock présent : False
avis.commentaire présent : False
paiements.reference_transaction présent : False
```

## Module 1 — Chapitre 0 : les trois bases démarrées
```text
NAME                         IMAGE         COMMAND                  SERVICE    CREATED         STATUS                   PORTS
senmarket-bases-mongo-1      mongo:7       "docker-entrypoint.s…"   mongo      2 minutes ago   Up 2 minutes (healthy)   127.0.0.1:27017->27017/tcp
senmarket-bases-postgres-1   postgres:16   "docker-entrypoint.s…"   postgres   2 minutes ago   Up 2 minutes (healthy)   127.0.0.1:5432->5432/tcp
senmarket-bases-redis-1      redis:7       "docker-entrypoint.s…"   redis      2 minutes ago   Up 2 minutes (healthy)   127.0.0.1:6379->6379/tcp
```
