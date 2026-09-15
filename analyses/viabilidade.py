# %%
import json
import pandas as pd

# %%

raw = pd.read_excel("data/viabilidade.xlsx")
raw.head()

# %%

raw["Tipo"].value_counts()

# %%

raw["Quantidade portas"].value_counts()

# %%

raw[raw["Tipo"] == "ZZ caixa emenda com spliter cliente"]
# %%

# %%

mask_cto = raw["Tipo"].str.contains("CTO", case=False, na=False)

df = raw[mask_cto]
ceo = raw[~mask_cto]

cols_numericas = [
    "Quantidade equip.", "Quantidade portas", "Portas ocupadas",
    "Portas livres", "Total portas reservadas", "Portas atendimento cliente",
]
df = df.dropna(subset=cols_numericas, how="all")

df[cols_numericas] = df[cols_numericas].fillna(0)
ceo[cols_numericas] = ceo[cols_numericas].fillna(0)

# %%
df["Tipo"].value_counts()

# %%

# %%
ctos = df

ctos["Tipo"].value_counts()

# %%

ceo["Tipo"].value_counts()
# %%
equipamentos = int(ctos["Quantidade equip."].sum())
portas = int(ctos["Quantidade portas"].sum())
portas_ocupadas = int(ctos["Portas ocupadas"].sum())
portas_livres = int(ctos["Portas livres"].sum())
portas_reservas = int(ctos["Total portas reservadas"].sum())
portas_cliente = int(ctos["Portas atendimento cliente"].sum())

resultado = {
    "resumo": {
        "CTOs": len(ctos),
        "CEOs": len(ceo),
        "Equipamentos": equipamentos,
    },
    "portas": {
        "Totais": portas,
        "Ocupadas": portas_ocupadas,
        "Livres": portas_livres,
        "Reservadas": portas_reservas,
        "Cliente": portas_cliente,
    },
}

validacao_portas = portas_cliente + portas_ocupadas + portas_livres + portas_reservas == portas
validacao_total = len(ctos) + len(ceo) == len(raw)

print(f"Validação portas (cliente + ocupadas + livres + reservadas == totais): {validacao_portas}")
print(f"Validação total (CTO + CEO == raw): {validacao_total}")

with open("output/results.json", "w", encoding="utf-8") as f:
    json.dump(resultado, f, ensure_ascii=False, indent=2)

# %%
table = ctos[[
    "Sigla", "Latitude", "Longitude", "Cidade", "Estado",
    "Quantidade equip.", "Quantidade portas", "Portas ocupadas",
    "Portas livres", "Total portas reservadas", "Portas bloqueadas", 
    "Portas atendimento cliente",
    "Tipo",
]].copy()

table.to_excel("output/ctos.xlsx", index=False)
# %%
