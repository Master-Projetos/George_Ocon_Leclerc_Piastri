import os
import json
import threading
import requests
import pandas as pd
from core.settings import get_settings
from core.constants import ALLOWED_RELATORIES, GEOGRID_URL

settings = get_settings()

GEOGRID_USER = settings.GEOGRID_USER
GEOGRID_PASS = settings.GEOGRID_PASSWORD

GEOGRID_API = GEOGRID_URL.rstrip("/") + "/api/v3"
GEOGRID_VERSION = "199.7"
REGISTROS_POR_PAGINA = 1000

# Map from the report's field names to the display column names the rest of the
# pipeline (treat_viabilidade / dashboard) already expects.
FIELD_MAP = {
    "sigla": "Sigla",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "cidade": "Cidade",
    "descricaoRecipienteTipo": "Tipo",
    "quantidadeEquipamentos": "Quantidade equip.",
    "quantidadePortas": "Quantidade portas",
    "quantidadePortasOcupadas": "Portas ocupadas",
    "quantidadePortasLivres": "Portas livres",
    "quantidadePortasClienteAtendimento": "Portas atendimento cliente",
}

export_lock = threading.Lock()

# In-memory status store, keyed by relatory name.
# Fine for a single-process app with one export at a time (export_lock);
# TODO: Use regis insted of a dict
export_status = {}

def set_status(relatory: str, step: str, status: str = "processing"):
    export_status[relatory] = {"step": step, "status": status}


def login():
    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "Geogrid-Version": GEOGRID_VERSION,
    })
    resp = session.post(f"{GEOGRID_API}/autenticar", json={
        "usuario": GEOGRID_USER,
        "senha": GEOGRID_PASS,
        "codigoSeguranca": "",
        "dadosDispositivo": {},
        "hashDispositivo": None,
    }, timeout=60)
    resp.raise_for_status()

    token = resp.json().get("autenticacao")
    if not token:
        raise RuntimeError("Login failed: no authentication token returned")

    session.headers["Authorization"] = token
    return session


def export_relatory(relatory: str, download_dir: str = None):
    if relatory not in ALLOWED_RELATORIES:
        raise RuntimeError("This relatory doesn't have support yet, try a valid one")

    if download_dir is None:
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        download_dir = os.path.join(PROJECT_ROOT, "data")
    os.makedirs(download_dir, exist_ok=True)

    set_status(relatory, step="login")
    session = login()

    registros = []
    pagina = 1
    total_paginas = None
    while True:
        resp = session.get(f"{GEOGRID_API}/relatorios/{relatory}", params={
            "pagina": pagina,
            "registrosPorPagina": REGISTROS_POR_PAGINA,
            "consultarTotais": "S" if pagina == 1 else "N",
            "modoProjeto[]": "N",
        }, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        pagina_registros = data.get("registros", [])
        registros.extend(pagina_registros)

        if total_paginas is None:
            total = int(data.get("totalRegistros", 0))
            total_paginas = max(1, -(-total // REGISTROS_POR_PAGINA))  # ceil

        set_status(relatory, step=f"baixando pagina {pagina}/{total_paginas}")

        if pagina >= total_paginas or not pagina_registros:
            break
        pagina += 1

    file_path = os.path.join(download_dir, f"{relatory}.json")
    with open(file_path, "w", encoding="utf-8") as fh:
        json.dump(registros, fh, ensure_ascii=False)

    set_status(relatory, step="Concluido", status="Done")


def run_export(relatory: str):
    with export_lock:
        try:
            export_relatory(relatory)
        except Exception as error:
            set_status(relatory, step=f"Falha: {error}", status="Error")
            raise


def treat_viabilidade():
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    data_dir = os.path.join(PROJECT_ROOT, "data")
    file_path = os.path.join(data_dir, "viabilidade.json")

    if not os.path.isfile(file_path):
        return None

    with open(file_path, encoding="utf-8") as fh:
        registros = json.load(fh)

    raw_df = pd.DataFrame(registros)
    raw_df = raw_df[[c for c in FIELD_MAP if c in raw_df.columns]].rename(columns=FIELD_MAP)

    mask_cto = raw_df["Tipo"].str.contains("CTO", case=False, na=False)

    cto_df = raw_df[mask_cto].copy()
    ceo_df = raw_df[~mask_cto].copy()

    cols_numericas = [
        "Quantidade equip.", "Quantidade portas", "Portas ocupadas",
        "Portas livres", "Portas atendimento cliente",
    ]
    for df in (cto_df, ceo_df):
        df[cols_numericas] = df[cols_numericas].apply(pd.to_numeric, errors="coerce")

    cto_df = cto_df.dropna(subset=cols_numericas, how="all")
    cto_df[cols_numericas] = cto_df[cols_numericas].fillna(0)

    cols_tabela = ["Sigla", "Latitude", "Longitude", "Cidade"] + cols_numericas
    cto_table = cto_df[cols_tabela].copy().fillna("")

    ceo_df = ceo_df.dropna(subset=cols_numericas, how="all")
    ceo_df[cols_numericas] = ceo_df[cols_numericas].fillna(0)
    ceo_table = ceo_df[cols_tabela].copy().fillna("")

    estatisticas = {
        "Equipamentos": int(cto_table["Quantidade equip."].sum()),
        "Portas": int(cto_table["Quantidade portas"].sum()),
        "Portas ocupadas": int(cto_table["Portas ocupadas"].sum()),
        "Portas livres": int(cto_table["Portas livres"].sum()),
        "Portas atendimento cliente": int(cto_table["Portas atendimento cliente"].sum()),
    }

    return {
        "estatisticas": estatisticas,
        "dataframe": cto_table.to_dict(orient="records"),
        "ceo": ceo_table.to_dict(orient="records"),
    }
