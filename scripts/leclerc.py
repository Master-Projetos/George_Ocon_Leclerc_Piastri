"""Codigo Leclerc, do nada bate e derruba a rede toda
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASE_URL = "https://morfeu.geogridmaps.com.br/rbc/api/v3"
HEADERS = {"Accept": "application/json", "api-key": os.getenv("API_KEY")}

ITEM_TYPES = "caixa", "terminal", "rack"
PAGE_SIZE = 200
DELAY = 1.0
RETRIES = 3
RETRY_WAIT = 5.0


IDS_PATH = os.path.join(OUTPUT_DIR, "ids.json")
PROGRESS_PATH = os.path.join(OUTPUT_DIR, "progress.json")
ITEMS_PATH = os.path.join(OUTPUT_DIR, "ports_items.json")
FINAL_PATH = os.path.join(OUTPUT_DIR, "ports_final.json")
MISMATCHES_PATH = os.path.join(OUTPUT_DIR, "mismatches.json")


def get(path, params):
    for attempt in range(1, RETRIES + 1):
        try:
            resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params, timeout=60)
            time.sleep(DELAY)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt == RETRIES:
                raise
            print(f"[error] {e} — attempt {attempt}/{RETRIES}, waiting {RETRY_WAIT:.0f}s")
            time.sleep(RETRY_WAIT)


def list_ids():
    if os.path.exists(IDS_PATH):
        ids = json.load(open(IDS_PATH, encoding="utf-8"))
        print(f"[itensRede] using saved ids from {IDS_PATH}: {len(ids)} ids")
        return ids

    ids = []
    page = 1
    while True:
        data = get("/itensRede", {
            "pagina": page,
            "registrosPorPagina": PAGE_SIZE,
            "item[]": ITEM_TYPES,
            "modoProjeto": "N",
        })
        records = data.get("registros", [])
        if not records:
            break
        ids.extend(r["dados"]["id"] for r in records)
        print(f"[itensRede] page {page}: {len(ids)} ids so far")
        page += 1

    json.dump(ids, open(IDS_PATH, "w", encoding="utf-8"))
    return ids


def item_record(item):
    portas = portas_entrada = ocupadas = livres = reservadas = reservadas_cliente = 0
    equipamentos = item.get("equipamentos", [])
    for eq in equipamentos:
        v = eq["viabilidade"]
        portas += int(v["saidas"])
        ocupadas += int(v["ocupadasTotal"])
        livres += int(v["livres"])
        portas_entrada += int(v.get("entradas", 0))
        reservadas += int(v.get("reservadas", 0))
        reservadas_cliente += int(v.get("reservadasCliente", 0))

    return {
        "nome": f"item_{item.get('idItemRede')}",
        "idItemRede": item.get("idItemRede"),
        "portas": portas,
        "portasEntrada": portas_entrada,
        "ocupadas": ocupadas,
        "livres": livres,
        "reservadas": reservadas,
        "reservadasCliente": reservadas_cliente,
        "equipamentos": len(equipamentos),
    }


def sum_ports(ids):
    start = 0
    total = 0
    occupied = 0
    free = 0
    items = []
    if os.path.exists(PROGRESS_PATH):
        state = json.load(open(PROGRESS_PATH, encoding="utf-8"))
        start = state["index"]
        total = state["total"]
        occupied = state["occupied"]
        free = state["free"]
        items = json.load(open(ITEMS_PATH, encoding="utf-8")) if os.path.exists(ITEMS_PATH) else []
        print(f"[ports] resuming from item {start + 1}/{len(ids)}, partial total {total}")

    for i in range(start, len(ids)):
        data = get("/equipamentos/itemRede/portas", {"itensRede": [ids[i]], "modoProjeto[]": "N"})
        for item in data.get("itensRede", []):
            record = item_record(item)
            items.append(record)
            total += record["portas"]
            occupied += record["ocupadas"]
            free += record["livres"]

        if (i + 1) % 50 == 0 or i + 1 == len(ids):
            json.dump(
                {"index": i + 1, "total": total, "occupied": occupied, "free": free},
                open(PROGRESS_PATH, "w", encoding="utf-8"),
            )
            json.dump(items, open(ITEMS_PATH, "w", encoding="utf-8"))
            print(f"[ports] item {i + 1}/{len(ids)} — total so far: {total}")

    return total, occupied, free, items


def main():
    ids = list_ids()
    print(f"Items found ({'/'.join(ITEM_TYPES)}): {len(ids)}")
    total, occupied, free, items = sum_ports(ids)
    print(f"TOTAL PORTS: {total}")
    print(f"OCCUPIED PORTS: {occupied}")
    print(f"FREE PORTS: {free}")

    empty = [it for it in items if it["equipamentos"] == 0]
    print(f"Items with 0 equipamentos: {len(empty)}/{len(items)} ({len(empty) / len(items):.1%})")
    diff = total - (occupied + free)
    print(f"Check (total - occupied - free): {diff}" + (" OK" if diff == 0 else " MISMATCH"))

    mismatches = [
        {**it, "diff": it["portas"] - (it["ocupadas"] + it["livres"])}
        for it in items
        if it["portas"] != it["ocupadas"] + it["livres"]
    ]
    if mismatches:
        json.dump(mismatches, open(MISMATCHES_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"[ports] {len(mismatches)} item(s) with mismatch — see {MISMATCHES_PATH}")
    elif os.path.exists(MISMATCHES_PATH):
        os.remove(MISMATCHES_PATH)

    json.dump(items, open(FINAL_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"[ports] saved {len(items)} items to {FINAL_PATH} (use dashboard/generate_data.py --source api)")

    os.remove(PROGRESS_PATH)
    os.remove(ITEMS_PATH)


if __name__ == "__main__":
    main()
