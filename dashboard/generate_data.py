"""Generates dashboard/data.json from a normalized data source.

Sources supported today:
  --source spreadsheet   Reads the "viability report" (.xlsx) exported from Geogrid.
                          Used by default because the current API pipeline
                          (sync_ports.py) only brings the aggregate port total,
                          not the per-item detail this normalizer needs.

Source planned for the future:
  --source api           Reads output/ports_final.json, once a collector exists
                          that brings per-item detail from the API. The
                          normalizer already exists (normalize_api) and produces
                          the SAME output schema as the spreadsheet — the
                          front-end doesn't change, it just points to a
                          data.json generated a different way.

The output schema (one item per CTO/box/equipment) is shared by both paths,
so the dashboard (template.html) is fully source-agnostic. Note: the dashboard
UI and this schema's field names stay in Portuguese on purpose — they mirror
the spreadsheet's own column names and the dashboard's Portuguese-speaking
business audience:

{
  "meta": {"fonte": "planilha"|"api", "geradoEm": "...", "arquivoOrigem": "...", "totalItens": N},
  "itens": [
    {"nome","cidade","estado","pasta","portas","portasEntrada","ocupadas",
     "livres","atendimentoCliente","reservadasCliente","bloqueadas","equipamentos"},
    ...
  ]
}
"""

import argparse
import glob
import json
import os
from datetime import datetime

import openpyxl

DEFAULT_OUTPUT = os.path.join(os.path.dirname(__file__), "data.json")


def _int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def find_spreadsheet() -> str:
    candidates = sorted(
        glob.glob(os.path.join(os.path.dirname(__file__), "..", "data", "*.xlsx")),
        key=os.path.getmtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("No .xlsx found in data/")
    return candidates[0]


def normalize_spreadsheet(path: str) -> list:
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb["Sheet1"]
    it = ws.iter_rows(values_only=True)
    header = list(next(it))
    idx = {c: header.index(c) for c in header}

    def g(row, column):
        i = idx.get(column)
        if i is None or i >= len(row):
            return None
        return row[i]

    items = []
    for row in it:
        name = (row[0] or "").strip()
        if not name:
            continue
        items.append({
            "nome": name,
            "cidade": (g(row, "Cidade") or "").strip() or None,
            "estado": (g(row, "Estado") or "").strip() or None,
            "pasta": (g(row, "Pasta") or "").strip() or None,
            "portas": _int(g(row, "Quantidade portas")),
            "portasEntrada": _int(g(row, "Quantidade portas de entrada")),
            "ocupadas": _int(g(row, "Portas ocupadas")),
            "livres": _int(g(row, "Portas livres")),
            "atendimentoCliente": _int(g(row, "Portas atendimento cliente")),
            "reservadasCliente": _int(g(row, "Portas reservadas (cliente)")),
            "bloqueadas": _int(g(row, "Portas bloqueadas")),
            "equipamentos": _int(g(row, "Quantidade equip.")),
        })
    return items


def normalize_api(path: str) -> list:
    """Normalizes output/ports_final.json to the same schema as the spreadsheet.
    City/State/Folder stay None until a per-item collector brings that in.
    """
    data = json.load(open(path, encoding="utf-8"))
    items = []
    for d in data:
        items.append({
            "nome": d.get("nome"),
            "cidade": None,
            "estado": None,
            "pasta": None,
            "portas": _int(d.get("portas")),
            "portasEntrada": _int(d.get("portasEntrada")),
            "ocupadas": _int(d.get("ocupadas")),
            "livres": _int(d.get("livres")),
            "atendimentoCliente": _int(d.get("atendimentoCliente")),
            "reservadasCliente": _int(d.get("reservadasCliente")),
            "bloqueadas": _int(d.get("bloqueadas")),
            "equipamentos": _int(d.get("equipamentos")),
        })
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["spreadsheet", "api"], default="spreadsheet")
    ap.add_argument("--file", help="Path to the .xlsx (source=spreadsheet) or .json (source=api). If omitted, uses the most recent file in data/ (spreadsheet) or output/ports_final.json (api).")
    ap.add_argument("--output", default=DEFAULT_OUTPUT)
    args = ap.parse_args()

    if args.source == "spreadsheet":
        path = args.file or find_spreadsheet()
        items = normalize_spreadsheet(path)
    else:
        path = args.file or os.path.join(os.path.dirname(__file__), "..", "output", "ports_final.json")
        items = normalize_api(path)

    output = {
        "meta": {
            "fonte": args.source,
            "geradoEm": datetime.now().isoformat(timespec="seconds"),
            "arquivoOrigem": os.path.basename(path),
            "totalItens": len(items),
        },
        "itens": items,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    size_mb = os.path.getsize(args.output) / 1_000_000
    print(f"[dashboard] {len(items):,} items from '{path}' -> {args.output} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
