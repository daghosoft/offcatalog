"""Processo di sync (separato dal web, a priorita' bassa). Uso: python -m offcatalog.worker <run_id>"""
from __future__ import annotations

import fcntl
import json
import os
import signal
import sys
import time
import traceback
from contextlib import contextmanager

from . import builder, source
from .config import Config
from .state import ERRORE, COMPLETATA, INTERROTTA, State

# fase: (percentuale iniziale, percentuale finale)
PHASES = {
    "controllo": (0, 1),
    "download": (1, 30),
    "decompressione": (30, 40),
    "costruzione": (40, 85),
    "indice": (85, 93),
    "controlli": (93, 95),
    "pubblicazione": (95, 99),
    "pulizia": (99, 100),
}


class StopRequested(Exception):
    pass


class Ctl:
    def __init__(self, st: State, run_id: int):
        self.st = st
        self.run_id = run_id
        self.signalled = False
        self._base, self._span = 0.0, 1.0
        self._last_pct = 0.0

    def check_stop_cheap(self):
        if self.signalled:
            raise StopRequested()

    def check_stop(self):
        self.check_stop_cheap()
        if self.st.stop_requested(self.run_id):
            raise StopRequested()

    def progress(self, **kw):
        self.st.update_progress(self.run_id, **kw)

    def log(self, line: str):
        self.st.log(self.run_id, line)

    def frac(self, f: float):
        now = time.time()
        if now - self._last_pct < 0.3 and f < 1:
            return
        self._last_pct = now
        self.st.set_pct(self.run_id, self._base + self._span * max(0.0, min(f, 1.0)))

    @contextmanager
    def phase(self, name: str):
        lo, hi = PHASES[name]
        self._base, self._span = float(lo), float(hi - lo)
        self.st.phase_start(self.run_id, name)
        self.st.set_phase(self.run_id, name, lo)
        self.log(f"fase: {name}")
        yield
        self.st.phase_end(self.run_id, name)
        self.st.set_pct(self.run_id, hi)


def execute(cfg: Config, st: State, run_id: int, ctl: Ctl) -> str:
    """Esegue (o riprende) tutte le fasi. Restituisce lo stato finale."""
    run = st.get_run(run_id)
    prev_src = json.loads(run["source"] or "{}")

    with ctl.phase("controllo"):
        src = source.head(cfg)
        if prev_src.get("etag") and not source.same_source(prev_src, src):
            ctl.log("l'export e' cambiato dall'ultima volta: ricostruzione da capo")
            try:
                os.remove(cfg.build_db)
            except FileNotFoundError:
                pass
        st.update_run(run_id, source=src)
        ctl.progress(bytes_total=src.get("size"))
    ctl.check_stop()

    with ctl.phase("download"):
        source.download(cfg, src, ctl)
    ctl.check_stop()

    with ctl.phase("decompressione"):
        source.decompress(cfg, src, ctl)
    ctl.check_stop()

    with ctl.phase("costruzione"):
        builder.build(cfg, src, run_id, ctl)

    with ctl.phase("indice"):
        builder.index(cfg, src, ctl)
        ctl.progress(catalog_bytes=cfg.build_db.stat().st_size)
    ctl.check_stop()

    with ctl.phase("controlli"):
        ok, results = builder.checks(cfg, ctl)
        st.update_run(run_id, controls=results)
        if not ok:
            bad = ", ".join(c["nome"] for c in results if not c["ok"])
            raise RuntimeError(f"controlli di plausibilita' falliti ({bad}): catalogo pubblicato invariato")
    ctl.check_stop()

    with ctl.phase("pubblicazione"):
        path = builder.publish(cfg, ctl)
        st.update_run(run_id, published=1, output_path=path)

    with ctl.phase("pulizia"):
        builder.cleanup(cfg, ctl)
    return COMPLETATA


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    run_id = int(argv[0])
    cfg = Config.from_env()
    st = State(cfg)
    try:
        os.nice(cfg.nice)
    except OSError:
        pass
    lock = open(cfg.lock_file, "a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 3  # un'altra sync e' attiva
    ctl = Ctl(st, run_id)
    signal.signal(signal.SIGTERM, lambda *_: setattr(ctl, "signalled", True))
    signal.signal(signal.SIGINT, lambda *_: setattr(ctl, "signalled", True))
    st.set_pid(run_id, os.getpid())
    run = st.get_run(run_id)
    ctl.progress(seg_start=time.time(), seg_pct0=run["pct"] if run else 0)
    try:
        final = execute(cfg, st, run_id, ctl)
        st.set_status(run_id, final)
        ctl.log("completata")
        return 0
    except StopRequested:
        ctl.log("interrotta")
        st.set_status(run_id, INTERROTTA)
        return 0
    except Exception as e:  # noqa: BLE001
        ctl.log("errore: " + "".join(traceback.format_exception_only(type(e), e)).strip())
        st.set_status(run_id, ERRORE, error=str(e) or type(e).__name__)
        return 1
    finally:
        st.set_pid(run_id, None)
        try:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
