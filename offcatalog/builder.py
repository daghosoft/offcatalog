"""Costruzione del catalogo: filtro a blocchi riprendibile, indice FTS5, controlli, pubblicazione."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone

from . import ATTRIBUTION, SCHEMA_VERSION, __version__
from .settings import META_KEYS, to_text
from .config import Config
from .filters import REASONS, RowFilter

PRODUCTS_DDL = """
CREATE TABLE IF NOT EXISTS products (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    brand TEXT,
    kcal_100g REAL NOT NULL,
    fat_100g REAL,
    saturated_fat_100g REAL,
    carbs_100g REAL,
    sugars_100g REAL,
    fiber_100g REAL,
    proteins_100g REAL,
    salt_100g REAL,
    serving_size TEXT,
    serving_g REAL,
    nutriscore_grade TEXT,
    nova_group INTEGER,
    last_modified_t INTEGER
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS _build_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    run_id INTEGER NOT NULL,
    pos INTEGER NOT NULL,
    rows_read INTEGER NOT NULL,
    kept INTEGER NOT NULL,
    scarti TEXT NOT NULL
);
"""
INSERT_SQL = "INSERT OR IGNORE INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"


def _connect(path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _meta_get(conn, key):
    r = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r[0] if r else None


def _meta_set(conn, **kv):
    for k, v in kv.items():
        conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)", (k, None if v is None else str(v)))


def build(cfg: Config, src: dict, run_id: int, ctl) -> dict:
    """Legge export.csv a blocchi e riempie build.db. Il segnaposto e le righe stanno nello stesso commit."""
    fresh = True
    if cfg.build_db.exists():
        try:
            c = _connect(cfg.build_db)
            row = c.execute("SELECT run_id FROM _build_state WHERE id=1").fetchone()
            c.close()
            fresh = not (row and row[0] == run_id)
        except sqlite3.DatabaseError:
            fresh = True
    if fresh:
        for suffix in ("", "-journal"):
            try:
                os.remove(str(cfg.build_db) + suffix)
            except FileNotFoundError:
                pass
    conn = _connect(cfg.build_db)
    conn.executescript(PRODUCTS_DDL)
    st = conn.execute("SELECT pos, rows_read, kept, scarti FROM _build_state WHERE id=1").fetchone()

    csv_size = cfg.csv_file.stat().st_size
    with open(cfg.csv_file, "rb", buffering=4 * 1024 * 1024) as f:
        header_line = f.readline()
        header = header_line.decode("utf-8", "replace").rstrip("\r\n").split("\t")
        header_end = f.tell()
        flt = RowFilter(header, cfg)
        if st is None:
            pos, rows_read, kept = header_end, 0, 0
            scarti = {r: 0 for r in REASONS}
            conn.execute("INSERT INTO _build_state VALUES (1,?,?,?,?,?)",
                         (run_id, pos, rows_read, kept, json.dumps(scarti)))
            conn.commit()
        else:
            pos, rows_read, kept = st[0], st[1], st[2]
            scarti = {r: 0 for r in REASONS}
            scarti.update(json.loads(st[3]))
            ctl.log(f"ripresa della costruzione dal byte {pos} ({rows_read} righe gia' lette)")
        if _meta_get(conn, "build_complete") == "1":
            conn.close()
            ctl.progress(rows_read=rows_read, kept=kept, scarti=scarti, csv_pos=csv_size)
            return {"rows_read": rows_read, "kept": kept, "scarti": scarti}
        f.seek(pos)
        ncols = flt.ncols
        last_log = time.time()
        blocks = 0
        while True:
            ctl.check_stop()
            lines = 0
            batch_bytes = 0
            eof = False
            cur = conn.cursor()
            while lines < cfg.block_size:
                raw = f.readline()
                if not raw:
                    eof = True
                    break
                batch_bytes += len(raw)
                lines += 1
                text = raw.decode("utf-8", "replace").rstrip("\r\n")
                if not text:
                    rows_read += 1
                    scarti["riga_malformata"] += 1
                    continue
                fields = text.split("\t")
                rows_read += 1
                if len(fields) != ncols:
                    scarti["riga_malformata"] += 1
                    continue
                rec, reason = flt.process(fields)
                if reason:
                    scarti[reason] += 1
                    continue
                cur.execute(INSERT_SQL, rec)
                if cur.rowcount == 0:
                    scarti["doppione"] += 1
                else:
                    kept += 1
            pos += batch_bytes
            done = eof
            if done:
                _meta_set(conn, rows_read=rows_read, products=kept, build_complete=1,
                          **{f"scarti_{k}": v for k, v in scarti.items()})
            conn.execute("UPDATE _build_state SET pos=?, rows_read=?, kept=?, scarti=? WHERE id=1",
                         (pos, rows_read, kept, json.dumps(scarti)))
            conn.commit()
            blocks += 1
            ctl.frac(pos / max(csv_size, 1))
            ctl.progress(rows_read=rows_read, kept=kept, scarti=dict(scarti), csv_pos=pos, csv_bytes=csv_size)
            if time.time() - last_log > 30:
                ctl.log(f"costruzione: {rows_read} righe lette, {kept} prodotti tenuti")
                last_log = time.time()
            if done:
                break
    conn.close()
    return {"rows_read": rows_read, "kept": kept, "scarti": scarti}


def index(cfg: Config, src: dict, ctl) -> None:
    """VACUUM, indice FTS5, meta finali, ANALYZE. Rieseguibile senza danni."""
    conn = _connect(cfg.build_db)
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='_build_state'").fetchone():
        conn.close()  # tabella gia' tolta a fine fase: indice gia' completo
        ctl.log("indice gia' completo")
        return
    conn.execute("DROP TABLE IF EXISTS products_fts")
    conn.commit()
    # VACUUM prima dell'indice: puo' rinumerare i rowid, e l'indice FTS5 vi fa riferimento
    conn.execute("VACUUM")
    ctl.log("indice di testo FTS5")
    conn.execute(
        "CREATE VIRTUAL TABLE products_fts USING fts5(name, brand, content='products', content_rowid='rowid',"
        " tokenize='unicode61 remove_diacritics 2', prefix='2 3')"
    )
    conn.execute("INSERT INTO products_fts(products_fts) VALUES ('rebuild')")
    n = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    _meta_set(
        conn,
        schema_version=SCHEMA_VERSION,
        built_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        source_url=src.get("url") or cfg.source_url,
        source_etag=src.get("etag"),
        source_last_modified=src.get("last_modified"),
        products=n,
        countries=",".join(cfg.countries),
        offcatalog_version=__version__,
        attribution=ATTRIBUTION,
        license="ODbL 1.0",
        **{f"setting_{k}": to_text(k, getattr(cfg, k)) for k in META_KEYS},
    )
    conn.commit()
    conn.execute("ANALYZE")
    conn.execute("DROP TABLE IF EXISTS _build_state")
    conn.commit()
    conn.close()
    ctl.progress(catalog_bytes=cfg.build_db.stat().st_size)


def get_published(cfg: Config) -> dict | None:
    """Informazioni sul catalogo pubblicato, lette dal file stesso."""
    p = cfg.output_db
    if not p.exists():
        return None
    info = {
        "data": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prodotti": None,
        "dimensione": p.stat().st_size,
        "data_export": None,
        "etag": None,
    }
    try:
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5)
        meta = dict(c.execute("SELECT key, value FROM meta").fetchall())
        c.close()
        info["data"] = meta.get("built_at") or info["data"]
        info["prodotti"] = int(meta["products"]) if meta.get("products") else None
        info["data_export"] = meta.get("source_last_modified")
        info["etag"] = meta.get("source_etag")
    except sqlite3.Error:
        pass
    return info


def checks(cfg: Config, ctl) -> tuple[bool, list[dict]]:
    """Controlli di plausibilita' prima di pubblicare."""
    out: list[dict] = []
    conn = sqlite3.connect(cfg.build_db, timeout=30)
    n = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    out.append({"nome": "prodotti_minimi", "ok": n >= cfg.min_products, "valore": n, "soglia": cfg.min_products})
    pub = get_published(cfg)
    if pub and pub.get("prodotti"):
        soglia = int(pub["prodotti"] * cfg.min_ratio)
        out.append({"nome": "rapporto_con_pubblicato", "ok": n >= soglia, "valore": n, "soglia": soglia})
    else:
        out.append({"nome": "rapporto_con_pubblicato", "ok": True, "valore": n, "soglia": None})
    integ = conn.execute("PRAGMA integrity_check").fetchone()[0]
    out.append({"nome": "integrity_check", "ok": integ == "ok", "valore": integ, "soglia": "ok"})
    fts_ok, fts_val = False, "errore"
    try:
        conn.execute("INSERT INTO products_fts(products_fts) VALUES ('integrity-check')")
        row = conn.execute("SELECT name FROM products ORDER BY rowid LIMIT 1").fetchone()
        if row is None:
            fts_val = "catalogo vuoto"
        else:
            m = re.search(r"[^\W_]+", row[0], re.UNICODE)
            if m:
                q = '"' + m.group(0).replace('"', "") + '"*'
                hits = conn.execute(
                    "SELECT COUNT(*) FROM products_fts WHERE products_fts MATCH ?", (q,)
                ).fetchone()[0]
                fts_ok, fts_val = hits > 0, f"{hits} risultati per {q}"
            else:
                fts_val = "nessun termine da cercare"
    except sqlite3.Error as e:
        fts_val = str(e)
    out.append({"nome": "indice_fts5", "ok": fts_ok, "valore": fts_val, "soglia": ">0 risultati"})
    conn.close()
    return all(c["ok"] for c in out), out


def publish(cfg: Config, ctl) -> str:
    """Copia in .tmp nella cartella di uscita e sostituzione atomica con os.replace."""
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    tmp = cfg.output_dir / (cfg.output_db.name + ".tmp")
    total = cfg.build_db.stat().st_size
    done = 0
    with open(cfg.build_db, "rb") as src, open(tmp, "wb") as dst:
        while True:
            chunk = src.read(8 * 1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)
            done += len(chunk)
            ctl.frac(done / max(total, 1))
        dst.flush()
        os.fsync(dst.fileno())
    os.chmod(tmp, 0o644)
    os.replace(tmp, cfg.output_db)
    return str(cfg.output_db)


def cleanup(cfg: Config, ctl) -> None:
    if cfg.keep_work:
        ctl.log("pulizia saltata (OFFCAT_KEEP_WORK)")
        return
    for p in (cfg.csv_file, cfg.csv_part, cfg.csv_ok, cfg.gz_file, cfg.gz_part, cfg.download_info, cfg.build_db):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
