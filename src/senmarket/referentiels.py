"""Référentiels métier de SenMarket : villes, noms, vendeurs, produits.

Ces listes sont des données de référence écrites une fois pour toutes. Les poids servent aux
tirages pondérés (np.random.Generator.choice(..., p=...)) : ils sont normalisés au moment du
tirage, donc ils n'ont pas besoin de faire exactement 1.
"""

# (ville, région, poids) : Dakar ≈ un tiers des clients, puis les grandes villes, puis une longue traîne
VILLES = [
    ("Dakar", "Dakar", 33.0),
    ("Pikine", "Dakar", 7.0),
    ("Guédiawaye", "Dakar", 4.0),
    ("Rufisque", "Dakar", 3.5),
    ("Thiès", "Thiès", 7.0),
    ("Mbour", "Thiès", 5.0),
    ("Tivaouane", "Thiès", 1.5),
    ("Touba", "Diourbel", 6.0),
    ("Diourbel", "Diourbel", 1.5),
    ("Saint-Louis", "Saint-Louis", 5.0),
    ("Richard-Toll", "Saint-Louis", 1.2),
    ("Kaolack", "Kaolack", 4.5),
    ("Ziguinchor", "Ziguinchor", 3.5),
    ("Louga", "Louga", 2.0),
    ("Fatick", "Fatick", 1.5),
    ("Kolda", "Kolda", 1.3),
    ("Tambacounda", "Tambacounda", 1.5),
    ("Matam", "Matam", 1.0),
    ("Kaffrine", "Kaffrine", 1.0),
    ("Kédougou", "Kédougou", 0.6),
    ("Sédhiou", "Sédhiou", 0.6),
]

PRENOMS = [
    "Aïssatou", "Fatou", "Ndèye Fatou", "Awa", "Mariama", "Khady", "Aminata", "Coumba",
    "Seynabou", "Adja", "Bineta", "Rokhaya", "Dieynaba", "Mame Diarra", "Astou", "Ramatoulaye",
    "Ndèye", "Sokhna", "Yacine", "Maïmouna",
    "Cheikh", "Moussa", "Ibrahima", "Mamadou", "Abdoulaye", "Ousmane", "Modou", "Serigne",
    "Babacar", "Pape", "Alioune", "Omar", "Lamine", "Souleymane", "El Hadji", "Malick",
    "Assane", "Ibou", "Saliou", "Mouhamed",
]

NOMS = [
    "Diop", "Ndiaye", "Fall", "Sow", "Diallo", "Sène", "Mbaye", "Faye", "Gueye", "Ba",
    "Cissé", "Sarr", "Thiam", "Diouf", "Kane", "Ndour", "Sy", "Camara", "Diagne", "Seck",
    "Touré", "Badji", "Mendy", "Niang", "Dieng", "Wade", "Lô", "Sall", "Tall", "Ndao",
]

DOMAINES_EMAIL = [("gmail.com", 55), ("yahoo.fr", 15), ("orange.sn", 12), ("hotmail.com", 10), ("outlook.com", 8)]

PREFIXES_TELEPHONE = ["70", "75", "76", "77", "78"]  # opérateurs mobiles sénégalais

PREFIXES_BOUTIQUE = ["Boutique", "Chez", "Ets", "Comptoir", "Maison"]

# (nom_produit, categorie, prix_catalogue_xof) : 40 produits, 7 catégories, entre 1 000 et 500 000 XOF
PRODUITS = [
    ("Smartphone Tecno Spark 20", "telephonie", 75_000),
    ("Smartphone Samsung Galaxy A15", "telephonie", 115_000),
    ("Smartphone Itel A70", "telephonie", 45_000),
    ("iPhone 13 reconditionné", "telephonie", 320_000),
    ("Écouteurs sans fil", "telephonie", 9_500),
    ("Chargeur rapide 25 W", "telephonie", 4_000),
    ("Batterie externe 20 000 mAh", "telephonie", 13_500),
    ("Coque de protection", "telephonie", 2_500),
    ("Pagne wax 6 yards", "mode_tissus", 12_000),
    ("Bazin riche 5 m", "mode_tissus", 35_000),
    ("Boubou brodé homme", "mode_tissus", 45_000),
    ("Robe en wax", "mode_tissus", 18_000),
    ("Sandales en cuir", "mode_tissus", 10_000),
    ("Sac à main en cuir", "mode_tissus", 22_000),
    ("Riz brisé parfumé 25 kg", "alimentation", 17_500),
    ("Huile végétale 5 L", "alimentation", 6_500),
    ("Sucre en morceaux 5 kg", "alimentation", 4_000),
    ("Lait en poudre 400 g", "alimentation", 2_600),
    ("Café Touba 500 g", "alimentation", 2_000),
    ("Thé vert 250 g", "alimentation", 1_500),
    ("Oignons 25 kg", "alimentation", 12_500),
    ("Bouilloire électrique", "maison", 9_000),
    ("Matelas 2 places", "maison", 85_000),
    ("Set de casseroles", "maison", 27_000),
    ("Ventilateur sur pied", "maison", 21_000),
    ("Moustiquaire imprégnée", "maison", 5_000),
    ("Réfrigérateur 180 L", "electromenager", 210_000),
    ("Climatiseur 12 000 BTU", "electromenager", 285_000),
    ("Téléviseur LED 43 pouces", "electromenager", 175_000),
    ("Mixeur blender", "electromenager", 18_500),
    ("Fer à repasser", "electromenager", 8_500),
    ("Cuisinière 4 feux", "electromenager", 145_000),
    ("Beurre de karité 250 g", "beaute", 3_000),
    ("Parfum 100 ml", "beaute", 25_000),
    ("Mèches brésiliennes", "beaute", 30_000),
    ("Savon noir artisanal", "beaute", 1_200),
    ("Ordinateur portable 15 pouces", "informatique", 395_000),
    ("Clé USB 64 Go", "informatique", 6_000),
    ("Imprimante multifonction", "informatique", 95_000),
    ("Routeur 4G", "informatique", 39_000),
]

NB_VENDEURS = 20

# Paiements (écarts métier volontaires, voir le contrat)
METHODES_PAIEMENT = [("wave", 45), ("orange_money", 35), ("carte", 8), ("especes", 12)]
STATUTS_PAIEMENT = [("reussi", 90), ("echoue", 6), ("en_attente", 4)]

QUANTITES = [(1, 55), (2, 25), (3, 10), (4, 6), (5, 4)]
