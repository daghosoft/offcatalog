"""state.db: esecuzioni, fasi, registro e piccole chiavi di stato. Creato in modo idempotente."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager

from .config import Config

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin TEXT NOT NULL,
    force INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    phase TEXT,
    pct REAL NOT NULL DEFAULT 0,
    started_at REAL NOT NULL,
    finished_at REAL,
    error TEXT,
    stop_requested INTEGER NOT NULL DEFAULT 0,
    progress TEXT NOT NULL DEFAULT '{}',
    source TEXT NOT NULL DEFAULT '{}',
    controls TEXT NOT NULL DEFAULT '[]',
    published INTEGER NOT NULL DEFAULT 0,
    output_path TEXT,
    pid INTEGER
);
CREATE TABLE IF NOT EXISTS phases (
    run_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL,
    PRIMARY KEY (run_id, name)
);
CREATE TABLE IF NOT EXISTS log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    ts REAL NOT NULL,
    line TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS log_run ON log(run_id, id);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at REAL NOT NULL);
"""

# stati
IN_CORSO = "in_corso"
COMPLETATA = "completata"
NESSUNA_NOVITA = "nessuna_novita"
INTERROTTA = "interrotta"
ERRORE = "errore"


class State:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        cfg.work_dir.mkdir(parents=True, exist_ok=True)
        with self._c() as c:
            c.executescript(SCHEMA)
            self._prune(c)

    @contextmanager
    def _c(self):
        conn = sqlite3.connect(self.cfg.state_db, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _prune(self, c):
        keep = self.cfg.runs_keep
        row = c.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1 OFFSET ?", (keep,)).fetchone()
        if row:
            old = row["id"]
            for t in ("runs", "phases", "log"):
                col = "id" if t == "runs" else "run_id"
                c.execute(f"DELETE FROM {t} WHERE {col} <= ?", (old,))

    # ---- esecuzioni
    def create_run(self, origin: str, force: bool, status: str = IN_CORSO, source: dict | None = None) -> int:
        now = time.time()
        with self._c() as c:
            cur = c.execute(
                "INSERT INTO runs(origin, force, status, started_at, source, finished_at) VALUES (?,?,?,?,?,?)",
                (origin, int(force), status, now, json.dumps(source or {}),
                 None if status == IN_CORSO else now),
            )
            return cur.lastrowid

    def get_run(self, run_id: int):
        with self._c() as c:
            return c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()

    def latest_run(self):
        with self._c() as c:
            return c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()

    def active_run(self):
        """Esecuzione in corso o interrotta/in errore da riprendere (l'ultima, se non e' conclusa)."""
        with self._c() as c:
            return c.execute(
                "SELECT * FROM runs WHERE status IN (?,?) ORDER BY id DESC LIMIT 1", (IN_CORSO, INTERROTTA)
            ).fetchone()

    def recent_runs(self, n: int = 20):
        with self._c() as c:
            return c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (n,)).fetchall()

    def set_status(self, run_id: int, status: str, error: str | None = None):
        end = None if status == IN_CORSO else time.time()
        with self._c() as c:
            c.execute(
                "UPDATE runs SET status=?, error=?, finished_at=? WHERE id=?",
                (status, error, end, run_id),
            )

    def reopen(self, run_id: int):
        with self._c() as c:
            c.execute(
                "UPDATE runs SET status=?, error=NULL, finished_at=NULL, stop_requested=0 WHERE id=?",
                (IN_CORSO, run_id),
            )

    def request_stop(self, run_id: int):
        with self._c() as c:
            c.execute("UPDATE runs SET stop_requested=1 WHERE id=?", (run_id,))

    def stop_requested(self, run_id: int) -> bool:
        with self._c() as c:
            r = c.execute("SELECT stop_requested FROM runs WHERE id=?", (run_id,)).fetchone()
            return bool(r and r["stop_requested"])

    def set_pid(self, run_id: int, pid: int | None):
        with self._c() as c:
            c.execute("UPDATE runs SET pid=? WHERE id=?", (pid, run_id))

    def set_phase(self, run_id: int, phase: str, pct: float):
        with self._c() as c:
            c.execute("UPDATE runs SET phase=?, pct=? WHERE id=?", (phase, pct, run_id))

    def set_pct(self, run_id: int, pct: float):
        with self._c() as c:
            c.execute("UPDATE runs SET pct=? WHERE id=?", (pct, run_id))

    def update_progress(self, run_id: int, **kw):
        with self._c() as c:
            r = c.execute("SELECT progress FROM runs WHERE id=?", (run_id,)).fetchone()
            d = json.loads(r["progress"]) if r else {}
            d.update(kw)
            c.execute("UPDATE runs SET progress=? WHERE id=?", (json.dumps(d), run_id))

    def update_run(self, run_id: int, **cols):
        allowed = {"source", "controls", "published", "output_path"}
        sets, vals = [], []
        for k, v in cols.items():
            if k not in allowed:
                raise ValueError(k)
            sets.append(f"{k}=?")
            vals.append(json.dumps(v) if k in ("source", "controls") else v)
        with self._c() as c:
            c.execute(f"UPDATE runs SET {', '.join(sets)} WHERE id=?", (*vals, run_id))

    # ---- fasi e registro
    def phase_start(self, run_id: int, name: str):
        with self._c() as c:
            c.execute(
                "INSERT INTO phases(run_id,name,started_at) VALUES (?,?,?) "
                "ON CONFLICT(run_id,name) DO UPDATE SET ended_at=NULL",
                (run_id, name, time.time()),
            )

    def phase_end(self, run_id: int, name: str):
        with self._c() as c:
            c.execute("UPDATE phases SET ended_at=? WHERE run_id=? AND name=?", (time.time(), run_id, name))

    def phases(self, run_id: int):
        with self._c() as c:
            return c.execute(
                "SELECT * FROM phases WHERE run_id=? ORDER BY started_at, name", (run_id,)
            ).fetchall()

    def log(self, run_id: int, line: str):
        with self._c() as c:
            c.execute("INSERT INTO log(run_id, ts, line) VALUES (?,?,?)", (run_id, time.time(), line))

    def log_tail(self, run_id: int, n: int = 40):
        with self._c() as c:
            rows = c.execute(
                "SELECT ts, line FROM log WHERE run_id=? ORDER BY id DESC LIMIT ?", (run_id, n)
            ).fetchall()
        return list(reversed(rows))

    # ---- chiavi
    def kv_get(self, key: str):
        with self._c() as c:
            r = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
            return json.loads(r["value"]) if r else None

    def kv_set(self, key: str, value):
        with self._c() as c:
            c.execute(
                "INSERT INTO kv(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )

    # ---- impostazioni modificate dal pannello (override di env/default)
    def settings_get(self) -> dict:
        with self._c() as c:
            return {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM settings")}

    def settings_set(self, values: dict):
        now = time.time()
        with self._c() as c:
            for k, v in values.items():
                c.execute(
                    "INSERT INTO settings(key,value,updated_at) VALUES (?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                    (k, v, now),
                )

    def settings_delete(self, key: str):
        with self._c() as c:
            c.execute("DELETE FROM settings WHERE key=?", (key,))

    def mark_orphans_interrupted(self) -> int:
        """Esecuzioni rimaste 'in corso' senza processo (riavvio): le segna 'interrotta'."""
        with self._c() as c:
            cur = c.execute(
                "UPDATE runs SET status=?, finished_at=?, error=COALESCE(error,'processo terminato')"
                " WHERE status=?",
                (INTERROTTA, time.time(), IN_CORSO),
            )
            return cur.rowcount
