"""Sfoglia catalogo: /catalogo e /panel/catalogo (elenco, codice a barre, FTS sicura, pagine, file mancante, schema 1)."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from offcatalog import builder
from offcatalog.app import create_app

AUTH = ("admin", "changeme")


def build_db(path, n=120, schema="2"):
    conn = sqlite3.connect(path)
    if schema == "2":
        conn.executescript(builder.PRODUCTS_DDL)
        fts = "name, brand, generic_name"
    else:
        conn.executescript("""CREATE TABLE products (code TEXT PRIMARY KEY, name TEXT NOT NULL, brand TEXT,
            kcal_100g REAL NOT NULL, fat_100g REAL, saturated_fat_100g REAL, carbs_100g REAL, sugars_100g REAL,
            fiber_100g REAL, proteins_100g REAL, salt_100g REAL, serving_size TEXT, serving_g REAL,
            nutriscore_grade TEXT, nova_group INTEGER, last_modified_t INTEGER);
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);""")
        fts = "name, brand"
    for i in range(n):
        code = f"80000{i:08d}"
        name = f"Biscotto {i:03d}" if i % 2 == 0 else f"Pane integrale {i:03d}"
        if schema == "2":
            conn.execute("INSERT INTO products (code,name,brand,kcal_100g,fat_100g,generic_name,quantity,category) "
                         "VALUES (?,?,?,?,?,?,?,?)", (code, name, "Marca Uno", 400 + i, 1.5, "Descr " + name, "300 g", "en:snacks"))
        else:
            conn.execute("INSERT INTO products (code,name,brand,kcal_100g,fat_100g) VALUES (?,?,?,?,?)",
                         (code, name, "Marca Uno", 400 + i, 1.5))
    conn.execute("INSERT INTO products (code,name,brand,kcal_100g) VALUES (?,?,?,?)",
                 ("9000000000001", 'Dolce "speciale" (50%)', "L'Altra", 300) if schema == "1" else
                 ("9000000000001", 'Dolce "speciale" (50%)', "L'Altra", 300))
    conn.execute(f"CREATE VIRTUAL TABLE products_fts USING fts5({fts}, content='products', content_rowid='rowid',"
                 " tokenize='unicode61 remove_diacritics 2', prefix='2 3')")
    conn.execute("INSERT INTO products_fts(products_fts) VALUES ('rebuild')")
    conn.executemany("INSERT INTO meta VALUES (?,?)", [("schema_version", schema), ("built_at", "2026-11-19T10:00:00Z"),
                                                       ("products", str(n + 1))])
    conn.commit()
    conn.close()


@pytest.fixture
def env(make_cfg):
    cfg = make_cfg(no_auth=False, panel_user="admin", panel_password="changeme")
    app = create_app(cfg)
    return cfg, TestClient(app, client=("198.51.100.1", 1))


def get(c, **p):
    return c.get("/panel/catalogo", params=p, auth=AUTH)


def test_pagine_dietro_autenticazione(env):
    cfg, c = env
    for u in ("/catalogo", "/panel/catalogo"):
        assert c.get(u).status_code == 401
        assert c.get(u, auth=("admin", "no")).status_code == 401
    r = c.get("/catalogo", auth=AUTH)
    assert r.status_code == 200 and "Catalogo" in r.text and 'href="/settings"' in r.text and 'class="tab cur"' in r.text


def test_schede_su_tutte_le_pagine(env):
    cfg, c = env
    for u, cur in (("/", "Dashboard"), ("/catalogo", "Catalogo"), ("/settings", "Impostazioni")):
        t = c.get(u, auth=AUTH).text
        assert f'class="tab cur" href="{u}" aria-current="page">{cur}<' in t
        assert 'href="/catalogo"' in t and 'href="/"' in t


def test_file_mancante(env):
    cfg, c = env
    r = get(c)
    assert r.status_code == 404 and r.json()["errore"] == "Nessun catalogo pubblicato"


def test_elenco_e_paginazione(env):
    cfg, c = env
    build_db(cfg.output_db)
    j = get(c).json()
    assert j["totale"] == 121 and j["pagine"] == 3 and len(j["righe"]) == 50 and j["pagina"] == 1
    assert j["info"]["file"] == cfg.output_name and j["info"]["schema"] == "2" and j["info"]["prodotti"] == 121
    assert j["colonne"][:6] == ["code", "name", "brand", "generic_name", "quantity", "category"]
    assert j["righe"][0]["name"] == "Biscotto 000"
    j3 = get(c, pagina=3).json()
    assert len(j3["righe"]) == 21 and get(c, pagina=4).json()["righe"] == []
    codes = {r["code"] for p in (1, 2, 3) for r in get(c, pagina=p).json()["righe"]}
    assert len(codes) == 121
    assert get(c, pagina=0).json()["pagina"] == 1


def test_codice_a_barre(env):
    cfg, c = env
    build_db(cfg.output_db)
    j = get(c, q="8000000000005").json()
    assert j["modo"] == "barcode" and j["totale"] == 1 and j["righe"][0]["name"] == "Pane integrale 005"
    assert get(c, q="8999999999999").json()["totale"] == 0
    assert get(c, q="1234567").json()["modo"] == "testo"   # 7 cifre: non e' un codice


def test_fts_prefisso_e_marca(env):
    cfg, c = env
    build_db(cfg.output_db)
    j = get(c, q="bisc").json()
    assert j["modo"] == "testo" and j["totale"] == 60
    assert get(c, q="pane integrale 01").json()["totale"] == 5    # parole in AND, prefisso sull'ultima
    assert get(c, q="marca uno").json()["totale"] == 120


@pytest.mark.parametrize("q", ['"', '"biscotto', "bisc*", "(pane", "pane)", "a AND", "NOT", "name:pane", "^x", "x -y",
                               "'; DROP TABLE products; --", "***", "()", "a OR b", "\\"])
def test_fts_caratteri_speciali_mai_500(env, q):
    cfg, c = env
    build_db(cfg.output_db)
    r = get(c, q=q)
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert isinstance(r.json()["totale"], int)
    assert get(c).json()["totale"] == 121     # tabella intatta


def test_fts_apici_e_parentesi_trovano(env):
    cfg, c = env
    build_db(cfg.output_db)
    j = get(c, q='"speciale" (50%)').json()
    assert j["totale"] == 1 and j["righe"][0]["code"] == "9000000000001"
    assert get(c, q="l'altra").json()["totale"] == 1


def test_schema_1(env):
    cfg, c = env
    build_db(cfg.output_db, n=10, schema="1")
    j = get(c).json()
    assert j["info"]["schema"] == "1" and j["totale"] == 11
    assert "generic_name" not in j["colonne"] and "quantity" not in j["colonne"] and "category" not in j["colonne"]
    assert get(c, q="biscotto").json()["totale"] == 5
    assert get(c, q="8000000000002").json()["righe"][0]["name"] == "Biscotto 002"


def test_sola_lettura_e_nome_effettivo(env):
    cfg, c = env
    build_db(cfg.output_db, n=5)
    other = cfg.output_dir / "altro.db"
    build_db(other, n=20)
    assert get(c).json()["totale"] == 6
    r = c.post("/panel/settings", json={"output_name": "altro.db"}, headers={"X-Requested-With": "panel"}, auth=AUTH)
    assert r.status_code == 200
    j = get(c).json()
    assert j["info"]["file"] == "altro.db" and j["totale"] == 21
    # il file non e' stato modificato dalla lettura (nessun journal residuo)
    assert not list(cfg.output_dir.glob("*-journal")) and not list(cfg.output_dir.glob("*-wal"))


def test_file_corrotto_503(env):
    cfg, c = env
    cfg.output_db.write_bytes(b"non e' un database sqlite" * 50)
    assert get(c).status_code == 503
