"""API, pannello e processo di sync reale (sottoprocesso) contro un server HTTP locale."""
import time

import pytest
from fastapi.testclient import TestClient

from offcatalog.app import create_app
from offcatalog.state import INTERROTTA

LOCAL = ("127.0.0.1", 50000)
OUTSIDE = ("203.0.113.9", 50000)
RUN_KEYS = {"run_id", "stato", "origine", "forzata", "fase", "percentuale", "inizio", "fine", "durata_s",
            "stima_secondi_rimanenti", "fasi", "byte_scaricati", "byte_totali", "velocita_bps", "csv_bytes",
            "righe_lette", "prodotti_tenuti", "scarti", "doppioni", "catalogo_bytes", "controlli", "pubblicato",
            "percorso_uscita", "errore", "sorgente", "link", "settings"}


@pytest.fixture
def env(source_factory, make_cfg, csv_gz):
    gz, _, _ = csv_gz
    src = source_factory(gz)
    cfg = make_cfg(src.url, no_auth=False, panel_user="admin", panel_password="changeme")
    app = create_app(cfg)
    return cfg, app, src


def wait_done(client, run_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        r = client.get(f"/api/runs/{run_id}").json()
        if r["stato"] != "in_corso":
            return r
        time.sleep(0.2)
    raise AssertionError("sync non terminata")


def test_regola_indirizzi_api(env):
    cfg, app, src = env
    out = TestClient(app, client=OUTSIDE)
    for r in (out.post("/api/sync"), out.get("/api/status"), out.get("/api/runs/1")):
        assert r.status_code == 403
    docker = TestClient(app, client=("172.18.0.1", 1))
    assert docker.get("/api/status").status_code == 200
    # anche con le credenziali del pannello, da fuori e' 403
    assert out.get("/api/status", auth=("admin", "changeme")).status_code == 403


def test_sync_end_to_end_202_409_200(env):
    cfg, app, src = env
    c = TestClient(app, client=LOCAL)
    r = c.post("/api/sync")
    assert r.status_code == 202
    body = r.json()
    assert set(body) == {"run_id", "esito", "origine", "sorgente", "catalogo_pubblicato", "link"}
    assert body["esito"] == "avviata" and body["origine"] == "endpoint"
    assert body["sorgente"]["etag"] == '"v1"' and body["sorgente"]["dimensione"] == len(src.payload)
    assert body["link"] == f"/api/runs/{body['run_id']}"
    # seconda chiamata mentre e' in corso
    r2 = c.post("/api/sync")
    assert r2.status_code == 409 and r2.json()["esito"] == "gia_in_corso" and r2.json()["run_id"] == body["run_id"]
    run = wait_done(c, body["run_id"])
    assert run["stato"] == "completata", run
    assert set(run) == RUN_KEYS
    assert run["pubblicato"] is True and run["prodotti_tenuti"] == 40 and run["righe_lette"] == 49
    assert run["scarti"]["paese"] == 1 and run["doppioni"] == 1 and run["percentuale"] == 100
    assert [f["nome"] for f in run["fasi"]] == sorted(
        ["controllo", "download", "decompressione", "costruzione", "indice", "controlli", "pubblicazione", "pulizia"],
        key=["controllo", "download", "decompressione", "costruzione", "indice", "controlli", "pubblicazione",
             "pulizia"].index)
    assert all(ch["ok"] for ch in run["controlli"])
    assert cfg.output_db.exists() and not cfg.build_db.exists() and not cfg.csv_file.exists()
    # export invariato: 200 nessuna novita'
    r3 = c.post("/api/sync")
    assert r3.status_code == 200 and r3.json()["esito"] == "nessuna_novita"
    assert r3.json()["catalogo_pubblicato"]["prodotti"] == 40
    # forzata: riparte
    r4 = c.post("/api/sync?force=1")
    assert r4.status_code == 202
    assert wait_done(c, r4.json()["run_id"])["stato"] == "completata"
    st = c.get("/api/status").json()
    assert st["in_corso"] is False and st["catalogo_pubblicato"]["prodotti"] == 40
    assert st["ultima_chiamata_api"]["esito"] == "avviata"
    assert set(st["esecuzione"]) == RUN_KEYS
    assert c.get("/api/runs/9999").status_code == 404


def test_esecuzione_interrotta_blocca_con_409_e_si_riprende(env):
    cfg, app, src = env
    c = TestClient(app, client=LOCAL)
    mgr = app.state.manager
    rid = mgr.st.create_run("pannello", False)
    mgr.st.set_status(rid, INTERROTTA, error="prova")
    r = c.post("/api/sync")
    assert r.status_code == 409 and r.json()["esito"] == "interrotta" and r.json()["run_id"] == rid
    p = TestClient(app, client=("198.51.100.1", 1))
    h = {"X-Requested-With": "panel"}
    res = p.post("/panel/cmd/riprendi", headers=h, auth=("admin", "changeme")).json()
    assert res["esito"] == "ripresa" and res["run_id"] == rid
    assert wait_done(c, rid)["stato"] == "completata"
    assert p.post("/panel/cmd/riprendi", headers=h, auth=("admin", "changeme")).json()["esito"] == "niente_da_riprendere"


def test_pannello_comandi_idle(env):
    cfg, app, src = env
    p = TestClient(app, client=("198.51.100.1", 1))
    a, h = ("admin", "changeme"), {"X-Requested-With": "panel"}
    assert p.post("/panel/cmd/interrompi", headers=h, auth=a).json()["esito"] == "niente_in_corso"
    assert p.post("/panel/cmd/avvia", auth=a).status_code == 403  # manca l'intestazione anti-CSRF
    assert p.post("/panel/cmd/boh", headers=h, auth=a).status_code == 404
    res = p.post("/panel/cmd/riparti", headers=h, auth=a).json()
    assert res["esito"] == "avviata"
    assert wait_done(TestClient(app, client=LOCAL), res["run_id"])["stato"] == "completata"
    d = p.get("/panel/data", auth=a).json()
    assert d["storico"][0]["stato"] == "completata" and d["log"] and d["stato"]["catalogo_pubblicato"]["prodotti"] == 40


def test_auth_pannello(env):
    cfg, app, src = env
    c = TestClient(app, client=("198.51.100.1", 1))
    r = c.get("/")
    assert r.status_code == 401 and "Basic" in r.headers["www-authenticate"]
    assert c.get("/", auth=("admin", "sbagliata")).status_code == 401
    assert c.get("/", auth=("altro", "changeme")).status_code == 401
    assert c.get("/panel/data").status_code == 401
    ok = c.get("/", auth=("admin", "changeme"))
    assert ok.status_code == 200 and "offcatalog" in ok.text
    assert c.get("/health").status_code == 200  # senza credenziali


def test_rifiuta_di_partire_senza_password(make_cfg):
    with pytest.raises(RuntimeError):
        create_app(make_cfg(no_auth=False))
    with pytest.raises(RuntimeError):
        create_app(make_cfg(no_auth=False, panel_user="admin"))
    create_app(make_cfg(no_auth=True))  # sviluppo locale


def test_no_auth_esplicito(make_cfg):
    app = create_app(make_cfg(no_auth=True))
    assert TestClient(app, client=("198.51.100.1", 1)).get("/").status_code == 200


def test_stato_iniziale_e_idempotenza(make_cfg):
    cfg = make_cfg(no_auth=True)
    app = create_app(cfg)
    assert cfg.state_db.exists()
    create_app(cfg)  # secondo avvio sullo stesso state.db
    c = TestClient(app, client=LOCAL)
    st = c.get("/api/status").json()
    assert st["esecuzione"] is None and st["catalogo_pubblicato"]["data"] is None and st["in_corso"] is False


def test_esecuzione_rimasta_a_meta_diventa_interrotta(make_cfg):
    cfg = make_cfg(no_auth=True)
    app = create_app(cfg)
    rid = app.state.manager.st.create_run("pannello", False)  # "in corso" senza processo
    app2 = create_app(cfg)  # riavvio
    assert TestClient(app2, client=LOCAL).get(f"/api/runs/{rid}").json()["stato"] == "interrotta"


def test_controlli_falliti_lasciano_il_catalogo_pubblicato(env, make_cfg, source_factory, csv_gz):
    cfg, app, src = env
    c = TestClient(app, client=LOCAL)
    rid = c.post("/api/sync").json()["run_id"]
    assert wait_done(c, rid)["stato"] == "completata"
    before = cfg.output_db.read_bytes()
    app2 = create_app(cfg.with_(min_products=1000))
    c2 = TestClient(app2, client=LOCAL)
    r = c2.post("/api/sync?force=1")
    assert r.status_code == 202
    run = wait_done(c2, r.json()["run_id"])
    assert run["stato"] == "errore" and "prodotti_minimi" in run["errore"] and run["pubblicato"] is False
    assert [x["ok"] for x in run["controlli"]][0] is False
    assert cfg.output_db.read_bytes() == before
    assert not (cfg.output_dir / "off_catalog.db.tmp").exists()
