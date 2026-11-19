"""Applicazione web: pannello (HTTP Basic), API per il cron (per indirizzo), /health."""
from __future__ import annotations

import base64
import binascii
import ipaddress
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import __version__
from .config import Config
from .manager import Manager, iso
from .panel import PANEL_HTML

STATUS_CODE = {"avviata": 202, "nessuna_novita": 200, "gia_in_corso": 409, "interrotta": 409}


def create_app(cfg: Config | None = None, manager: Manager | None = None) -> FastAPI:
    cfg = cfg or Config.from_env()
    if not cfg.no_auth and not (cfg.panel_user and cfg.panel_password):
        raise RuntimeError(
            "OFFCAT_PANEL_USER e OFFCAT_PANEL_PASSWORD sono obbligatori (oppure OFFCAT_NO_AUTH=1 in sviluppo)"
        )
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    mgr = manager or Manager(cfg)
    nets = cfg.networks()
    app = FastAPI(title="offcatalog", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.manager = mgr
    app.state.cfg = cfg

    def api_allowed(request: Request) -> bool:
        host = request.client.host if request.client else None
        try:
            ip = ipaddress.ip_address(host)
        except (ValueError, TypeError):
            return False
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return any(ip in n for n in nets if n.version == ip.version)

    def forbidden():
        return JSONResponse({"errore": "indirizzo non ammesso"}, status_code=403)

    def panel_ok(request: Request) -> bool:
        if cfg.no_auth:
            return True
        h = request.headers.get("authorization", "")
        if not h.lower().startswith("basic "):
            return False
        try:
            user, _, pw = base64.b64decode(h[6:]).decode("utf-8").partition(":")
        except (binascii.Error, UnicodeDecodeError):
            return False
        ok_u = secrets.compare_digest(user.encode(), cfg.panel_user.encode())
        ok_p = secrets.compare_digest(pw.encode(), cfg.panel_password.encode())
        return ok_u and ok_p

    def unauthorized():
        return JSONResponse({"errore": "autenticazione richiesta"}, status_code=401,
                            headers={"WWW-Authenticate": 'Basic realm="offcatalog"'})

    # ---- salute
    @app.get("/health")
    def health():
        return {"status": "ok", "versione": __version__}

    # ---- API per il cron
    @app.post("/api/sync")
    def api_sync(request: Request, force: int = 0):
        if not api_allowed(request):
            return forbidden()
        esito, run_id, src = mgr.start("endpoint", force=bool(force))
        mgr.record_api_call(esito, run_id)
        body = {
            "run_id": run_id,
            "esito": esito,
            "origine": "endpoint",
            "sorgente": mgr.source_view(src),
            "catalogo_pubblicato": mgr.published_view(),
            "link": f"/api/runs/{run_id}" if run_id else None,
        }
        return JSONResponse(body, status_code=STATUS_CODE[esito])

    @app.get("/api/status")
    def api_status(request: Request):
        if not api_allowed(request):
            return forbidden()
        return mgr.status_view()

    @app.get("/api/runs/{run_id}")
    def api_run(request: Request, run_id: int):
        if not api_allowed(request):
            return forbidden()
        v = mgr.run_view(run_id)
        if v is None:
            return JSONResponse({"errore": "esecuzione inesistente"}, status_code=404)
        return v

    # ---- pannello
    @app.get("/", response_class=HTMLResponse)
    def panel(request: Request):
        if not panel_ok(request):
            return unauthorized()
        return HTMLResponse(PANEL_HTML)

    @app.get("/panel/data")
    def panel_data(request: Request):
        if not panel_ok(request):
            return unauthorized()
        status = mgr.status_view()
        last = status["esecuzione"]
        log = []
        if last:
            log = [{"ts": iso(r["ts"]), "line": r["line"]} for r in mgr.st.log_tail(last["run_id"], 60)]
        locked, why = mgr.settings_lock()
        return {"versione": __version__, "stato": status, "storico": mgr.history_view(20), "log": log,
                "impostazioni_blocco": {"bloccato": locked, "motivo": why}}

    @app.get("/panel/settings")
    def panel_settings(request: Request):
        if not panel_ok(request):
            return unauthorized()
        return mgr.settings_view()

    @app.post("/panel/settings")
    async def panel_settings_save(request: Request):
        if not panel_ok(request):
            return unauthorized()
        if request.headers.get("x-requested-with") != "panel":
            return JSONResponse({"errore": "intestazione mancante"}, status_code=403)
        try:
            body = await request.json()
        except ValueError:
            body = None
        if not isinstance(body, dict) or not body:
            return JSONResponse({"errore": "corpo non valido: atteso un oggetto JSON con i campi da salvare"},
                                status_code=400)
        code, out = mgr.save_settings(body)
        return JSONResponse(out, status_code=code)

    @app.post("/panel/settings/reset/{key}")
    def panel_settings_reset(request: Request, key: str):
        if not panel_ok(request):
            return unauthorized()
        if request.headers.get("x-requested-with") != "panel":
            return JSONResponse({"errore": "intestazione mancante"}, status_code=403)
        code, out = mgr.reset_setting(key)
        return JSONResponse(out, status_code=code)

    @app.post("/panel/cmd/{name}")
    def panel_cmd(request: Request, name: str):
        if not panel_ok(request):
            return unauthorized()
        if request.headers.get("x-requested-with") != "panel":
            return JSONResponse({"errore": "intestazione mancante"}, status_code=403)
        if name in ("avvia", "forza"):
            esito, rid, _ = mgr.start("pannello", force=(name == "forza"))
            msg = {
                "avviata": "Sincronizzazione avviata.",
                "nessuna_novita": "Nessuna novita': l'export non e' cambiato (usa Forza per ricostruire).",
                "gia_in_corso": "Una sincronizzazione e' gia' in corso.",
                "interrotta": "C'e' un'esecuzione interrotta: usa Riprendi o Riparti da zero.",
            }[esito]
        elif name == "interrompi":
            esito, rid = ("interruzione_richiesta" if mgr.stop() else "niente_in_corso"), None
            msg = "Si fermera' a fine blocco." if esito == "interruzione_richiesta" else "Nessuna esecuzione in corso."
        elif name == "riprendi":
            esito, rid = mgr.resume()
            msg = {"ripresa": "Ripresa avviata.", "gia_in_corso": "Gia' in corso.",
                   "niente_da_riprendere": "Niente da riprendere."}[esito]
        elif name == "riparti":
            esito, rid, _ = mgr.restart_from_scratch()
            msg = "Ripartita da zero." if esito == "avviata" else "Una sincronizzazione e' gia' in corso."
        else:
            return JSONResponse({"errore": "comando sconosciuto"}, status_code=404)
        return {"esito": esito, "run_id": rid, "messaggio": msg}

    return app


def app_factory() -> FastAPI:
    """Per uvicorn: `uvicorn offcatalog.app:app_factory --factory`."""
    return create_app()
