import gzip
import os

import pytest

from conftest import FakeCtl
from offcatalog import source


def payload(n=300_000):
    return gzip.compress(os.urandom(n))


def test_head(source_factory, make_cfg):
    p = payload()
    s = source_factory(p)
    info = source.head(make_cfg(s.url))
    assert info["size"] == len(p) and info["etag"] == '"v1"' and info["last_modified"]


def test_download_completo(source_factory, make_cfg):
    p = payload()
    s = source_factory(p)
    cfg = make_cfg(s.url)
    cfg.work_dir.mkdir()
    source.download(cfg, source.head(cfg), FakeCtl())
    assert cfg.gz_file.read_bytes() == p and not cfg.gz_part.exists()


def test_ripresa_con_range_dopo_connessione_interrotta(source_factory, make_cfg):
    p = payload()
    s = source_factory(p)
    s.cut_after = 100_000
    cfg = make_cfg(s.url)
    cfg.work_dir.mkdir()
    ctl = FakeCtl()
    source.download(cfg, source.head(cfg), ctl)
    assert cfg.gz_file.read_bytes() == p
    gets = [r for r in s.requests if r[0] == "GET"]
    assert gets[0][1] is None and gets[1][1] == "bytes=100000-"
    assert any("nuovo tentativo" in line for line in ctl.logs)


def test_ripresa_da_part_esistente(source_factory, make_cfg):
    p = payload()
    s = source_factory(p)
    cfg = make_cfg(s.url)
    cfg.work_dir.mkdir()
    cfg.gz_part.write_bytes(p[:5000])
    source.download(cfg, source.head(cfg), FakeCtl())
    assert cfg.gz_file.read_bytes() == p
    assert [r for r in s.requests if r[0] == "GET"][0][1] == "bytes=5000-"


def test_server_che_ignora_range_riparte_da_zero(source_factory, make_cfg):
    p = payload()
    s = source_factory(p)
    s.ignore_range = True
    cfg = make_cfg(s.url)
    cfg.work_dir.mkdir()
    cfg.gz_part.write_bytes(p[:5000])
    source.download(cfg, source.head(cfg), FakeCtl())
    assert cfg.gz_file.read_bytes() == p


def test_sorgente_cambiata_scarta_il_part(source_factory, make_cfg):
    p1, p2 = payload(), payload()
    s = source_factory(p1, etag='"v1"')
    cfg = make_cfg(s.url)
    cfg.work_dir.mkdir()
    source.download(cfg, source.head(cfg), FakeCtl())
    cfg.gz_part.write_bytes(b"x" * 100)
    s.payload, s.etag = p2, '"v2"'
    source.download(cfg, source.head(cfg), FakeCtl())
    assert cfg.gz_file.read_bytes() == p2


def test_decompressione_e_riuso(source_factory, make_cfg):
    raw = b"a\tb\n1\t2\n" * 1000
    p = gzip.compress(raw)
    s = source_factory(p)
    cfg = make_cfg(s.url)
    cfg.work_dir.mkdir()
    src = source.head(cfg)
    source.download(cfg, src, FakeCtl())
    source.decompress(cfg, src, FakeCtl())
    assert cfg.csv_file.read_bytes() == raw
    ctl = FakeCtl()
    source.decompress(cfg, src, ctl)
    assert any("riuso" in line for line in ctl.logs)
