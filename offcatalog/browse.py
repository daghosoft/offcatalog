"""Sfoglia il catalogo pubblicato (sola lettura): elenco, codice a barre, ricerca di testo FTS5."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

PAGE_SIZE = 50
MAX_TOKENS = 8
BARCODE_RE = re.compile(r"[0-9]{8,14}")
TOKEN_RE = re.compile(r"\w+", re.UNICODE)

# colonne in ordine etichetta UE (le ultime tre assenti nello schema 1)
BASE_COLS = ["code", "name", "brand", "generic_name", "quantity", "category", "kcal_100g", "fat_100g",
             "saturated_fat_100g", "carbs_100g", "sugars_100g", "fiber_100g", "proteins_100g", "salt_100g"]
OPTIONAL = {"generic_name", "quantity", "category"}


def fts_query(q: str) -> str | None:
    """Testo libero -> query FTS5 sicura: ogni parola tra virgolette, prefisso sull'ultima. None se vuota."""
    toks = TOKEN_RE.findall(q)[:MAX_TOKENS]
    if not toks:
        return None
    parts = ['"%s"' % t for t in toks]
    parts[-1] += "*"
    return " ".join(parts)


def _meta(conn) -> dict:
    try:
        return dict(conn.execute("SELECT key, value FROM meta").fetchall())
    except sqlite3.Error:
        return {}


def search(path: Path, q: str, page: int) -> tuple[int, dict]:
    """Restituisce (codice HTTP, corpo JSON). Apre il file in sola lettura e lo chiude a fine richiesta."""
    if not path.exists():
        return 404, {"errore": "Nessun catalogo pubblicato", "pubblicato": False}
    q = (q or "").strip()[:200]
    page = max(1, page)
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return 503, {"errore": "Catalogo non leggibile in questo momento", "pubblicato": True}
    try:
        meta = _meta(conn)
        have = {r[1] for r in conn.execute("PRAGMA table_info(products)")}
        if not have:
            return 503, {"errore": "Catalogo non leggibile in questo momento", "pubblicato": True}
        cols = [c for c in BASE_COLS if c in have]
        sel = ", ".join("p." + c for c in cols)
        info = {"file": path.name, "schema": meta.get("schema_version") or "1", "prodotti": None,
                "data": meta.get("built_at"), "dimensione": path.stat().st_size}
        off = (page - 1) * PAGE_SIZE
        if q == "":
            mode = "tutti"
            total = int(meta["products"]) if (meta.get("products") or "").isdigit() else \
                conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            info["prodotti"] = total
            rows = conn.execute(f"SELECT {sel} FROM products p ORDER BY p.name COLLATE NOCASE, p.code LIMIT ? OFFSET ?",
                                (PAGE_SIZE, off)).fetchall()
        elif BARCODE_RE.fullmatch(q):
            mode = "barcode"
            rows = conn.execute(f"SELECT {sel} FROM products p WHERE p.code = ? LIMIT ? OFFSET ?",
                                (q, PAGE_SIZE, off)).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM products WHERE code = ?", (q,)).fetchone()[0]
        else:
            mode = "testo"
            match = fts_query(q)
            if match is None:
                rows, total = [], 0
            else:
                try:
                    total = conn.execute("SELECT COUNT(*) FROM products_fts WHERE products_fts MATCH ?",
                                         (match,)).fetchone()[0]
                    rows = conn.execute(
                        f"SELECT {sel} FROM products_fts f JOIN products p ON p.rowid = f.rowid "
                        "WHERE products_fts MATCH ? ORDER BY f.rank LIMIT ? OFFSET ?",
                        (match, PAGE_SIZE, off)).fetchall()
                except sqlite3.Error:
                    return 422, {"errore": "Ricerca non valida: prova con parole piu' semplici"}
        if info["prodotti"] is None:
            info["prodotti"] = int(meta["products"]) if (meta.get("products") or "").isdigit() else None
        pages = max(1, -(-total // PAGE_SIZE))
        return 200, {
            "pubblicato": True, "info": info, "modo": mode, "q": q, "pagina": page, "pagine": pages,
            "per_pagina": PAGE_SIZE, "totale": total, "colonne": cols,
            "righe": [dict(zip(cols, r)) for r in rows],
        }
    except sqlite3.Error:
        return 503, {"errore": "Catalogo non leggibile in questo momento", "pubblicato": True}
    finally:
        conn.close()
