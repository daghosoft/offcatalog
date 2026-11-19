"""Gestione delle esecuzioni: avvio del processo di sync, interrompi, riprendi, riparti da zero."""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import builder, source
from .config import Config
from .state import (COMPLETATA, ERRORE, IN_CORSO, INTERROTTA, NESSUNA_NOVITA, State)

SCARTI_KEYS = ("paese", "barcode", "nome", "kcal", "coerenza", "doppione", "riga_malformata")
SPAWN_GRACE = 20.0  # secondi concessi al processo di sync per prendere il lock


def iso(ts):
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def unchanged(src: dict, pub: dict | None) -> bool:
    """True se l'export e' lo stesso da cui e' nato il catalogo pubblicato."""
    if not pub:
        return False
    if src.get("etag") and pub.get("etag"):
        return src["etag"] == pub["etag"]
    if src.get("last_modified") and pub.get("data_export"):
        return src["last_modified"] == pub["data_export"]
    return False


class Manager:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.st = State(cfg)
        self.mu = threading.RLock()
        self._proc: subprocess.Popen | None = None
        self._spawn_ts = 0.0
        if not self.lock_held():
            self.st.mark_orphans_interrupted()

    # ---- processo
    def lock_held(self) -> bool:
        f = open(self.cfg.lock_file, "a+")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        finally:
            try:
                fcntl.flock(f, fcntl.LOCK_UN)
            except OSError:
                pass
            f.close()
        return False

    def reconcile(self):
        """Un'esecuzione 'in corso' senza processo vivo diventa 'interrotta'."""
        with self.mu:
            run = self.st.active_run()
            if not run or run["status"] != IN_CORSO:
                return
            if self._proc is not None:
                alive = self._proc.poll() is None
            else:
                alive = self.lock_held() or time.time() - self._spawn_ts < SPAWN_GRACE
            if not alive:
                self._proc = None
                if self.st.get_run(run["id"])["status"] == IN_CORSO:
                    self.st.set_status(run["id"], INTERROTTA, error="processo di sync terminato")

    def _spawn(self, run_id: int):
        self.cfg.work_dir.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, **self.cfg.to_env()}
        root = str(Path(__file__).resolve().parent.parent)
        log = open(self.cfg.work_dir / "worker.log", "ab")
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "offcatalog.worker", str(run_id)],
            env=env, cwd=root, stdout=log, stderr=log, start_new_session=True,
        )
        log.close()
        self._spawn_ts = time.time()

    # ---- comandi
    def start(self, origin: str, force: bool = False) -> tuple[str, int | None, dict]:
        """Avvia una sync. Esiti: avviata, gia_in_corso, interrotta, nessuna_novita."""
        with self.mu:
            self.reconcile()
            active = self.st.active_run()
            if active:
                esito = "gia_in_corso" if active["status"] == IN_CORSO else "interrotta"
                return esito, active["id"], json.loads(active["source"] or "{}")
            src = source.head_safe(self.cfg)
            if not force and unchanged(src, builder.get_published(self.cfg)):
                rid = self.st.create_run(origin, force, status=NESSUNA_NOVITA, source=src)
                self.st.log(rid, "export invariato: nessuna novita'")
                return "nessuna_novita", rid, src
            rid = self.st.create_run(origin, force, source=src)
            self.st.log(rid, f"esecuzione avviata ({origin}{', forzata' if force else ''})")
            self._spawn(rid)
            return "avviata", rid, src

    def stop(self) -> bool:
        with self.mu:
            self.reconcile()
            run = self.st.active_run()
            if run and run["status"] == IN_CORSO:
                self.st.request_stop(run["id"])
                self.st.log(run["id"], "interruzione richiesta: si ferma a fine blocco")
                return True
            return False

    def resumable(self):
        last = self.st.latest_run()
        if last and last["status"] in (INTERROTTA, ERRORE):
            return last
        return None

    def resume(self) -> tuple[str, int | None]:
        with self.mu:
            self.reconcile()
            last = self.st.latest_run()
            if last and last["status"] == IN_CORSO:
                return "gia_in_corso", last["id"]
            run = self.resumable()
            if not run:
                return "niente_da_riprendere", None
            self.st.reopen(run["id"])
            self.st.log(run["id"], "ripresa richiesta")
            self._spawn(run["id"])
            return "ripresa", run["id"]

    def restart_from_scratch(self, origin: str = "pannello") -> tuple[str, int | None, dict]:
        with self.mu:
            self.reconcile()
            last = self.st.latest_run()
            if last and last["status"] == IN_CORSO:
                return "gia_in_corso", last["id"], json.loads(last["source"] or "{}")
            if last and last["status"] == INTERROTTA:
                self.st.set_status(last["id"], ERRORE, error="sostituita da 'riparti da zero'")
            try:
                os.remove(self.cfg.build_db)
            except FileNotFoundError:
                pass
            return self.start(origin, force=True)

    # ---- viste
    def source_view(self, src: dict | None) -> dict:
        src = src or {}
        return {"url": src.get("url"), "etag": src.get("etag"),
                "last_modified": src.get("last_modified"), "dimensione": src.get("size")}

    def published_view(self) -> dict:
        pub = builder.get_published(self.cfg)
        if not pub:
            return {"data": None, "prodotti": None, "dimensione": None, "data_export": None}
        return {k: pub[k] for k in ("data", "prodotti", "dimensione", "data_export")}

    def run_view(self, run_id: int) -> dict | None:
        self.reconcile()
        r = self.st.get_run(run_id)
        if not r:
            return None
        prog = json.loads(r["progress"] or "{}")
        now = time.time()
        end = r["finished_at"] or now
        pct = round(r["pct"], 1)
        eta = None
        if r["status"] == IN_CORSO and "seg_start" in prog and pct - prog.get("seg_pct0", 0) > 1:
            elapsed = now - prog["seg_start"]
            eta = int(elapsed * (100 - pct) / (pct - prog["seg_pct0"]))
        scarti = prog.get("scarti")
        if scarti is not None:
            scarti = {k: scarti.get(k, 0) for k in SCARTI_KEYS}
        controls = json.loads(r["controls"] or "[]")
        phases = [
            {"nome": p["name"], "inizio": iso(p["started_at"]), "fine": iso(p["ended_at"]),
             "durata_s": round((p["ended_at"] or now) - p["started_at"], 1)}
            for p in self.st.phases(run_id)
        ]
        return {
            "run_id": r["id"],
            "stato": r["status"],
            "origine": r["origin"],
            "forzata": bool(r["force"]),
            "fase": r["phase"],
            "percentuale": pct,
            "inizio": iso(r["started_at"]),
            "fine": iso(r["finished_at"]),
            "durata_s": round(end - r["started_at"], 1),
            "stima_secondi_rimanenti": eta,
            "fasi": phases,
            "byte_scaricati": prog.get("bytes_downloaded"),
            "byte_totali": prog.get("bytes_total"),
            "velocita_bps": prog.get("speed"),
            "csv_bytes": prog.get("csv_bytes"),
            "righe_lette": prog.get("rows_read"),
            "prodotti_tenuti": prog.get("kept"),
            "scarti": scarti,
            "doppioni": scarti["doppione"] if scarti else None,
            "catalogo_bytes": prog.get("catalog_bytes"),
            "controlli": controls or None,
            "pubblicato": bool(r["published"]),
            "percorso_uscita": r["output_path"],
            "errore": r["error"],
            "sorgente": self.source_view(json.loads(r["source"] or "{}")),
            "link": f"/api/runs/{r['id']}",
        }

    def status_view(self) -> dict:
        self.reconcile()
        last = self.st.latest_run()
        active = self.st.active_run()
        return {
            "in_corso": bool(active and active["status"] == IN_CORSO),
            "in_attesa_di_ripresa": bool(self.resumable()),
            "esecuzione": self.run_view(last["id"]) if last else None,
            "catalogo_pubblicato": self.published_view(),
            "ultima_chiamata_api": self.st.kv_get("last_api"),
        }

    def history_view(self, n: int = 20) -> list[dict]:
        out = []
        for r in self.st.recent_runs(n):
            prog = json.loads(r["progress"] or "{}")
            out.append({
                "run_id": r["id"], "origine": r["origin"], "stato": r["status"],
                "inizio": iso(r["started_at"]),
                "durata_s": round((r["finished_at"] or time.time()) - r["started_at"], 1),
                "prodotti_tenuti": prog.get("kept"), "errore": r["error"], "pubblicato": bool(r["published"]),
            })
        return out

    def record_api_call(self, esito: str, run_id: int | None):
        self.st.kv_set("last_api", {"data": iso(time.time()), "esito": esito, "run_id": run_id})
