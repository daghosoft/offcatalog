import json
import sqlite3

import pytest

from conftest import FakeCtl, sample_rows
from offcatalog import builder
from offcatalog.worker import StopRequested

SRC = {"url": "http://example.invalid/x", "etag": '"v1"', "last_modified": "Thu, 19 Nov 2026 10:00:00 GMT", "size": 1}


def setup_csv(cfg, text):
    cfg.work_dir.mkdir(parents=True, exist_ok=True)
    cfg.csv_file.write_text(text, encoding="utf-8")


def rows_of(path):
    c = sqlite3.connect(path)
    r = c.execute("SELECT * FROM products ORDER BY code").fetchall()
    c.close()
    return r


def test_costruzione_da_csv_sintetico(make_cfg, csv_gz):
    _, text, expected = csv_gz
    cfg = make_cfg()
    setup_csv(cfg, text)
    ctl = FakeCtl()
    res = builder.build(cfg, SRC, 1, ctl)
    assert res["kept"] == 40
    assert res["rows_read"] == 40 + 9
    assert {k: v for k, v in res["scarti"].items() if v} == expected
    builder.index(cfg, SRC, ctl)
    c = sqlite3.connect(cfg.build_db)
    meta = dict(c.execute("SELECT key, value FROM meta").fetchall())
    assert meta["schema_version"] == "2" and meta["products"] == "40" and meta["rows_read"] == "49"
    assert meta["source_etag"] == '"v1"' and meta["scarti_paese"] == "1" and "ODbL" in meta["attribution"]
    assert "_build_state" not in [r[0] for r in c.execute("SELECT name FROM sqlite_master")]
    # FTS: prefisso e senza accenti
    c.execute("UPDATE products SET name='Caffè macinato' WHERE code='8000000000000'")
    c.execute("INSERT INTO products_fts(products_fts) VALUES ('rebuild')")
    hit = c.execute("SELECT p.code FROM products_fts f JOIN products p ON p.rowid=f.rowid "
                    "WHERE products_fts MATCH 'caffe*'").fetchall()
    assert hit == [("8000000000000",)]
    assert c.execute("SELECT COUNT(*) FROM products_fts WHERE products_fts MATCH 'tost*'").fetchone()[0] == 39
    c.close()


def test_ripresa_dopo_interruzione_nessuna_riga_persa_o_doppia(make_cfg, csv_gz, tmp_path):
    _, text, _ = csv_gz
    # riferimento: costruzione senza interruzioni
    ref = make_cfg().with_(work_dir=tmp_path / "ref")
    setup_csv(ref, text)
    r_ref = builder.build(ref, SRC, 1, FakeCtl())

    cfg = make_cfg()
    setup_csv(cfg, text)
    expected_rows = 0
    for stop_at in (1, 2, 3):
        with pytest.raises(StopRequested):
            builder.build(cfg, SRC, 7, FakeCtl(stop_after_blocks=stop_at))
        c = sqlite3.connect(cfg.build_db)
        pos, rows = c.execute("SELECT pos, rows_read FROM _build_state").fetchone()
        n = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        c.close()
        expected_rows += 7 * stop_at  # ogni ripresa fa stop_at blocchi dal punto salvato
        assert rows == expected_rows and n <= rows  # il segnaposto e le righe sono nello stesso commit
    res = builder.build(cfg, SRC, 7, FakeCtl())
    assert res["rows_read"] == r_ref["rows_read"] and res["kept"] == r_ref["kept"]
    assert res["scarti"] == r_ref["scarti"]
    assert rows_of(cfg.build_db) == rows_of(ref.build_db)


def test_nuova_esecuzione_ricostruisce_da_capo(make_cfg, csv_gz):
    _, text, _ = csv_gz
    cfg = make_cfg()
    setup_csv(cfg, text)
    with pytest.raises(StopRequested):
        builder.build(cfg, SRC, 1, FakeCtl(stop_after_blocks=2))
    res = builder.build(cfg, SRC, 2, FakeCtl())  # altro run_id: riparte
    assert res["kept"] == 40 and res["rows_read"] == 49


def test_controlli_di_plausibilita(make_cfg, csv_gz):
    _, text, _ = csv_gz
    cfg = make_cfg(min_products=100)
    setup_csv(cfg, text)
    builder.build(cfg, SRC, 1, FakeCtl())
    builder.index(cfg, SRC, FakeCtl())
    ok, res = builder.checks(cfg, FakeCtl())
    assert not ok
    assert {c["nome"]: c["ok"] for c in res}["prodotti_minimi"] is False
    cfg2 = cfg.with_(min_products=10)
    ok, res = builder.checks(cfg2, FakeCtl())
    assert ok and all(c["ok"] for c in res)
    assert {c["nome"] for c in res} == {"prodotti_minimi", "rapporto_con_pubblicato", "integrity_check", "indice_fts5"}


def test_controllo_rapporto_con_pubblicato(make_cfg, csv_gz):
    _, text, _ = csv_gz
    cfg = make_cfg(min_products=1)
    setup_csv(cfg, text)
    builder.build(cfg, SRC, 1, FakeCtl())
    builder.index(cfg, SRC, FakeCtl())
    builder.publish(cfg, FakeCtl())
    assert builder.get_published(cfg)["prodotti"] == 40
    ok, _ = builder.checks(cfg, FakeCtl())
    assert ok  # 40 su 40
    # export parziale: meno dell'80% del pubblicato
    c = sqlite3.connect(cfg.build_db)
    c.execute("DELETE FROM products WHERE rowid > 20")
    c.execute("INSERT INTO products_fts(products_fts) VALUES ('rebuild')")
    c.commit()
    c.close()
    ok, res = builder.checks(cfg, FakeCtl())
    assert not ok
    assert [c for c in res if c["nome"] == "rapporto_con_pubblicato"][0]["soglia"] == 32


def test_pubblicazione_atomica(make_cfg, csv_gz, monkeypatch):
    _, text, _ = csv_gz
    cfg = make_cfg()
    setup_csv(cfg, text)
    builder.build(cfg, SRC, 1, FakeCtl())
    builder.index(cfg, SRC, FakeCtl())
    cfg.output_dir.mkdir()
    cfg.output_db.write_bytes(b"vecchio catalogo")
    seen = {}
    real = builder.os.replace

    def spy(a, b):
        # al momento della sostituzione il vecchio file e' intatto e il nuovo e' completo accanto
        seen["old"] = cfg.output_db.read_bytes()
        seen["tmp"] = str(a)
        seen["tmp_size"] = (cfg.output_dir / "off_catalog.db.tmp").stat().st_size
        real(a, b)

    monkeypatch.setattr(builder.os, "replace", spy)
    builder.publish(cfg, FakeCtl())
    assert seen["old"] == b"vecchio catalogo"
    assert seen["tmp"].endswith("off_catalog.db.tmp") and seen["tmp_size"] == cfg.build_db.stat().st_size
    assert not (cfg.output_dir / "off_catalog.db.tmp").exists()
    assert builder.get_published(cfg)["prodotti"] == 40
    assert sqlite3.connect(cfg.output_db).execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_v2_contesto_e_fts_su_generic_name(make_cfg):
    from conftest import HEADER, make_csv, make_row
    header = HEADER + ["generic_name", "categories"]
    text = make_csv([make_row(header, generic_name="Crema spalmabile alle nocciole", categories="Dolci, Creme")], header)
    cfg = make_cfg(min_products=1)
    setup_csv(cfg, text)
    builder.build(cfg, SRC, 1, FakeCtl())
    builder.index(cfg, SRC, FakeCtl())
    c = sqlite3.connect(cfg.build_db)
    assert c.execute("SELECT generic_name, quantity, category FROM products").fetchone() == (
        "Crema spalmabile alle nocciole", "300 g", "Creme")
    assert dict(c.execute("SELECT key, value FROM meta").fetchall())["schema_version"] == "2"
    hit = c.execute("SELECT p.code FROM products_fts f JOIN products p ON p.rowid=f.rowid "
                    "WHERE products_fts MATCH 'nocciol*'").fetchall()
    assert len(hit) == 1
    c.close()


def test_nome_output_di_default(make_cfg):
    cfg = make_cfg()
    assert cfg.output_name == "off_catalog.db"
    assert cfg.output_db == cfg.output_dir / "off_catalog.db"


def test_nome_output_custom_da_env_e_to_env(tmp_path):
    from offcatalog.config import Config
    cfg = Config.from_env({"OFFCAT_OUTPUT_NAME": "off_catalog_v2.db", "OFFCAT_OUTPUT_DIR": str(tmp_path)})
    assert cfg.output_db.name == "off_catalog_v2.db"
    assert cfg.to_env()["OFFCAT_OUTPUT_NAME"] == "off_catalog_v2.db"


def test_nome_output_custom_usato_dalla_pubblicazione(make_cfg, csv_gz):
    _, text, _ = csv_gz
    cfg = make_cfg().with_(output_name="off_catalog_v2.db")
    setup_csv(cfg, text)
    builder.build(cfg, SRC, 1, FakeCtl())
    builder.index(cfg, SRC, FakeCtl())
    builder.publish(cfg, FakeCtl())
    assert (cfg.output_dir / "off_catalog_v2.db").exists()
    assert not (cfg.output_dir / "off_catalog.db").exists()
    assert not (cfg.output_dir / "off_catalog_v2.db.tmp").exists()
    assert builder.get_published(cfg)["prodotti"] == 40


@pytest.mark.parametrize("nome", ["../x.db", "a/b.db", "x.txt", "..db.db", "", "a b.db", "/etc/x.db"])
def test_nome_output_non_valido_rifiutato(nome):
    from offcatalog.config import Config
    with pytest.raises(ValueError, match="OFFCAT_OUTPUT_NAME"):
        Config.from_env({"OFFCAT_OUTPUT_NAME": nome})
