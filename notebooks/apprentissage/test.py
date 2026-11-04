from senmarket.generateur import generer_verite

tables = generer_verite("2026-10-29", rows=10000)

for nom, df in tables.items():
    print(nom, df.shape)

print(tables["commandes"].head())
print(tables["lignes_commande"].head(10))