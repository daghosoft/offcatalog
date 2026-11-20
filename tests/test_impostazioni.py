"""Impostazioni modificabili dal pannello: precedenza, validazione, blocco, reset, tracciabilita'."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from offcatalog.app import create_app
from offcatalog.config import Config
from offcatalog.state import INTERROTTA

from test_api import LOCAL, wait_done

AUTH = ("admin", "changeme")
H = {"X-Requested-With": "panel"}


@pytest.fixture
def env(source_factory, make_cfg, csv_gz):
    src = source_factory(csv_gz[0])
    cfg = make_cfg(src.url, no_auth=False, panel_user="admin", panel_password="changeme")
    app = create_app(cfg)
    return cfg, app, TestClient(app, client=("198.51.100.1", 1))


def post(c, body):
    return c.post("/panel/settings", json=body, headers=H, auth=AUTH)


def campo(c, key):
    return next(f for f in c.get("/panel/settings", auth=AUTH).json()["campi"] if f["chiave"] == key)


def test_precedenza_override_env_default(tmp_path):
    env = {"OFFCAT_WORK_DIR": str(tmp_path / "w"), "OFFCAT_OUTPUT_DIR": str(tmp_path / "o"), "OFFCAT_NO_AUTH": "1"}
    assert Config.from_env({**env}).kcal_max == 900.0                      # default del codice
    cfg = Config.from_env({**env, "OFFCAT_KCAL_MAX": "800"})
    assert cfg.kcal_max == 800.0                                           # env > default
    app = create_app(cfg)
    c = TestClient(app, client=LOCAL)
    assert post(c, {"kcal_max": 700, "countries": "en:italy, en:france"}, ).status_code == 200
    eff = app.state.manager.effective_cfg()
    assert eff.kcal_max == 700.0 and eff.countries == ("en:italy", "en:france")   # override > env
    assert eff.to_env()["OFFCAT_KCAL_MAX"] == "700.0" and eff.to_env()["OFFCAT_COUNTRIES"] == "en:italy,en:france"
    f = campo(c, "kcal_max")
    assert f["valore"] == 700.0 and f["default"] == 800.0 and f["sovrascritto"] is True
    assert c.post("/panel/settings/reset/kcal_max", headers=H).status_code == 200
    assert app.state.manager.effective_cfg().kcal_max == 800.0              # reset: torna all'env
    assert campo(c, "kcal_max")["sovrascritto"] is False


@pytest.mark.parametrize("body,campo_err", [
    ({"kcal_min": -1}, "kcal_min"),
    ({"kcal_max": 2001}, "kcal_max"),
    ({"kcal_min": 500, "kcal_max": 500}, "kcal_max"),
    ({"kcal_max": 0.5}, "kcal_max"),                  # <= kcal_min effettivo (1)
    ({"coherence_pct": 1.5}, "coherence_pct"),
    ({"coherence_abs": -3}, "coherence_abs"),
    ({"min_products": 1.5}, "min_products"),
    ({"min_products": -1}, "min_products"),
    ({"min_ratio": 2}, "min_ratio"),
    ({"countries": ""}, "countries"),
    ({"countries": "italy"}, "countries"),
    ({"countries": "en:Italy!"}, "countries"),
    ({"keep_work": "boh"}, "keep_work"),
    ({"output_name": "../x.db"}, "output_name"),
    ({"output_name": "a/b.db"}, "output_name"),
    ({"output_name": "x.txt"}, "output_name"),
    ({"output_name": ""}, "output_name"),
    ({"output_name": "a b.db"}, "output_name"),
    ({"output_name": 5}, "output_name"),
    ({"kcal_min": "abc"}, "kcal_min"),
    ({"source_url": "http://x"}, "source_url"),
    ({"password": "x"}, "password"),
])
def test_validazione(env, body, campo_err):
    cfg, app, c = env
    r = post(c, body)
    assert r.status_code == 422 and campo_err in r.json()["campi"]
    assert app.state.manager.st.settings_get() == {}      # niente salvato


def test_validazione_ok_e_normalizzazione(env):
    cfg, app, c = env
    r = post(c, {"countries": "EN:Italy, en:france,en:italy", "keep_work": True, "min_products": 5, "min_ratio": 0.5,
                 "coherence_pct": 0, "coherence_abs": 0, "kcal_min": 0, "kcal_max": 2000})
    assert r.status_code == 200
    eff = app.state.manager.effective_cfg()
    assert eff.countries == ("en:italy", "en:france") and eff.keep_work is True and eff.min_products == 5


def test_corpo_e_autenticazione(env):
    cfg, app, c = env
    assert c.post("/panel/settings", json={"kcal_min": 2}).status_code == 401
    assert c.post("/panel/settings", json={"kcal_min": 2}, auth=AUTH).status_code == 403   # manca X-Requested-With
    assert c.post("/panel/settings/reset/kcal_min", headers=H).status_code == 401
    assert c.get("/panel/settings").status_code == 401
    assert c.post("/panel/settings", content=b"no", headers=H, auth=AUTH).status_code == 400
    assert c.post("/panel/settings/reset/boh", headers=H, auth=AUTH).status_code == 404


def test_blocco_solo_con_sync_in_corso(env):
    cfg, app, c = env
    mgr = app.state.manager
    assert "Torna al pannello" in c.get("/settings", auth=AUTH).text and 'id="setsave"' in c.get("/settings", auth=AUTH).text
    assert c.get("/settings").status_code == 401
    mgr.st.create_run("pannello", False)                   # "in corso" (nessun processo: lo teniamo vivo col lock)
    mgr._spawn_ts = __import__("time").time()
    r = post(c, {"kcal_min": 5})
    assert r.status_code == 409 and "in corso" in r.json()["errore"]
    assert c.post("/panel/settings/reset/kcal_min", headers=H, auth=AUTH).status_code == 409
    page = c.get("/settings", auth=AUTH).text
    assert "Sync in corso: impostazioni non disponibili" in page and "Torna al pannello" in page
    assert 'id="setsave"' not in page
    assert "impostazioni_blocco" not in c.get("/panel/data", auth=AUTH).json()


def test_sync_interrotta_non_blocca(env):
    cfg, app, c = env
    mgr = app.state.manager
    rid = mgr.st.create_run("pannello", False)
    mgr.st.set_status(rid, INTERROTTA)
    assert post(c, {"kcal_min": 5}).status_code == 200
    assert c.post("/panel/settings/reset/kcal_min", headers=H, auth=AUTH).status_code == 200
    assert 'id="setsave"' in c.get("/settings", auth=AUTH).text


def test_settings_nel_run_e_nel_meta(env):
    cfg, app, c = env
    assert post(c, {"kcal_max": 850, "keep_work": True}).status_code == 200
    local = TestClient(app, client=LOCAL)
    rid = local.post("/api/sync").json()["run_id"]
    run = wait_done(local, rid)
    assert run["stato"] == "completata", run
    s = run["settings"]
    assert s["kcal_max"] == 850.0 and s["keep_work"] is True and s["countries"] == ["en:italy"]
    assert s["kcal_min"] == 1.0 and s["min_products"] == 10
    conn = sqlite3.connect(cfg.output_db)
    meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    conn.close()
    assert meta["setting_kcal_max"] == "850.0" and meta["setting_keep_work"] == "1"
    assert meta["setting_kcal_min"] == "1.0" and meta["setting_min_products"] == "10"
    assert meta["countries"] == "en:italy" and "setting_countries" not in meta
    assert meta["schema_version"]


def test_output_name_precedenza_e_pubblicazione(source_factory, make_cfg, csv_gz):
    src = source_factory(csv_gz[0])
    cfg = make_cfg(src.url, no_auth=False, panel_user="admin", panel_password="changeme").with_(
        output_name="da_env.db")
    app = create_app(cfg)
    c = TestClient(app, client=("198.51.100.1", 1))
    mgr = app.state.manager
    assert mgr.effective_cfg().output_name == "da_env.db"                    # env > default
    assert post(c, {"output_name": " dal_pannello.db "}).status_code == 200
    assert mgr.effective_cfg().output_name == "dal_pannello.db"              # pannello > env
    f = campo(c, "output_name")
    assert f["valore"] == "dal_pannello.db" and f["default"] == "da_env.db" and f["sovrascritto"] is True
    local = TestClient(app, client=LOCAL)
    run = wait_done(local, local.post("/api/sync").json()["run_id"])
    assert run["stato"] == "completata", run
    assert (cfg.output_dir / "dal_pannello.db").exists() and not (cfg.output_dir / "da_env.db").exists()
    assert run["settings"]["output_name"] == "dal_pannello.db"
    assert local.get("/api/status").json()["catalogo_pubblicato"]["prodotti"] == 40   # nome effettivo
    conn = sqlite3.connect(cfg.output_dir / "dal_pannello.db")
    meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    conn.close()
    assert "setting_output_name" not in meta
    assert c.post("/panel/settings/reset/output_name", headers=H, auth=AUTH).status_code == 200
    assert mgr.effective_cfg().output_name == "da_env.db"                    # reset: torna all'env
    assert local.get("/api/status").json()["catalogo_pubblicato"]["prodotti"] is None
