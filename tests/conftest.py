"""Fixture comuni: CSV sintetico, server HTTP locale con HEAD e Range, configurazione di prova."""
from __future__ import annotations

import gzip
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from offcatalog.config import Config

# Colonne dell'export (sottoinsieme, stessi nomi dell'export reale piu' qualche colonna riempitiva)
HEADER = [
    "code", "url", "creator", "last_modified_t", "product_name", "quantity", "brands", "countries_tags",
    "ingredients_text", "serving_size", "serving_quantity", "nutriscore_grade", "nova_group",
    "energy-kj_100g", "energy-kcal_100g", "energy_100g", "fat_100g", "saturated-fat_100g",
    "carbohydrates_100g", "sugars_100g", "fiber_100g", "proteins_100g", "salt_100g", "sodium_100g",
    "alcohol_100g",
]

DEFAULTS = {
    "code": "8000000000017", "url": "http://example.invalid/p", "creator": "test", "last_modified_t": "1700000000",
    "product_name": "Biscotti frollini", "quantity": "300 g", "brands": "Marca Uno, Altra", "countries_tags": "en:italy",
    "ingredients_text": "farina", "serving_size": "30 g", "serving_quantity": "30", "nutriscore_grade": "c",
    "nova_group": "4", "energy-kcal_100g": "480", "fat_100g": "20", "saturated-fat_100g": "8",
    "carbohydrates_100g": "65", "sugars_100g": "25", "fiber_100g": "3", "proteins_100g": "7", "salt_100g": "0.5",
}


def make_row(header=HEADER, **kw) -> str:
    d = dict(DEFAULTS)
    d.update({k.replace("__", "-"): v for k, v in kw.items()})
    return "\t".join(d.get(col, "") for col in header)


def make_csv(rows: list[str], header=HEADER) -> str:
    return "\t".join(header) + "\n" + "\n".join(rows) + "\n"


def sample_rows(n_good: int = 40) -> tuple[list[str], dict]:
    """Righe valide (codici distinti) e una per ogni motivo di scarto. Restituisce (righe, attesi)."""
    rows = []
    for i in range(n_good):
        rows.append(make_row(code=f"80000{i:08d}", product_name=f"Prodotto tostate {i}"))
    rows += [
        make_row(code="3000000000001", countries_tags="en:france"),                       # paese
        make_row(code="abc", ),                                                           # barcode
        make_row(code="123"),                                                             # barcode (corto)
        make_row(code="8111111111111", product_name=""),                                  # nome
        make_row(code="8111111111112", **{"energy-kcal_100g": "1500"}),                   # kcal alta
        make_row(code="8111111111113", **{"energy-kcal_100g": "", "energy_100g": ""}),    # kcal assente
        make_row(code="8111111111114", **{"energy-kcal_100g": "880", "fat_100g": "5",     # kJ scritti come kcal
                                           "carbohydrates_100g": "10", "proteins_100g": "5"}),
        make_row(code="80000" + f"{0:08d}", product_name="Doppione"),                     # doppione del primo
        "riga\tcorta",                                                                    # malformata
    ]
    expected = {"paese": 1, "barcode": 2, "nome": 1, "kcal": 2, "coerenza": 1, "doppione": 1,
                "riga_malformata": 1}
    return rows, expected


class Source:
    """Server HTTP con HEAD, GET e Range. `cut_after`: chiude la connessione dopo N byte al primo GET."""

    def __init__(self, payload: bytes, etag: str = '"v1"'):
        self.payload = payload
        self.etag = etag
        self.cut_after: int | None = None
        self.ignore_range = False
        self.requests: list[tuple[str, str | None]] = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _headers(self, status, length, extra=None):
                self.send_response(status)
                self.send_header("ETag", outer.etag)
                self.send_header("Last-Modified", "Thu, 19 Nov 2026 10:00:00 GMT")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()

            def do_HEAD(self):
                outer.requests.append(("HEAD", None))
                self._headers(200, len(outer.payload))

            def do_GET(self):
                rng = self.headers.get("Range")
                outer.requests.append(("GET", rng))
                data = outer.payload
                if rng and not outer.ignore_range:
                    start = int(rng.split("=")[1].split("-")[0])
                    body = data[start:]
                    self._headers(206, len(body), {"Content-Range": f"bytes {start}-{len(data) - 1}/{len(data)}"})
                else:
                    body = data
                    self._headers(200, len(body))
                if outer.cut_after is not None:
                    n, outer.cut_after = outer.cut_after, None
                    self.wfile.write(body[:n])
                    self.wfile.flush()
                    self.connection.close()
                    return
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/export.csv.gz"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class FakeCtl:
    """Sostituto del controllo del worker: raccoglie i log e puo' simulare 'Interrompi' dopo N blocchi."""

    def __init__(self, stop_after_blocks: int | None = None):
        self.stop_after_blocks = stop_after_blocks
        self.blocks = 0
        self.logs: list[str] = []
        self.prog: dict = {}

    def check_stop(self):
        if self.stop_after_blocks is not None and self.blocks >= self.stop_after_blocks:
            from offcatalog.worker import StopRequested
            raise StopRequested()

    check_stop_cheap = check_stop

    def progress(self, **kw):
        self.prog.update(kw)
        if "rows_read" in kw:
            self.blocks += 1

    def frac(self, f):
        pass

    def log(self, line):
        self.logs.append(line)


@pytest.fixture
def source_factory():
    made = []

    def make(payload: bytes, etag='"v1"'):
        s = Source(payload, etag)
        made.append(s)
        return s

    yield make
    for s in made:
        s.close()


@pytest.fixture
def csv_gz():
    rows, expected = sample_rows()
    text = make_csv(rows)
    return gzip.compress(text.encode("utf-8")), text, expected


@pytest.fixture
def make_cfg(tmp_path):
    def make(source_url="http://127.0.0.1:1/none", **kw):
        base = dict(
            work_dir=tmp_path / "work", output_dir=tmp_path / "out", source_url=source_url,
            min_products=10, block_size=7, retry_base=0.01, http_timeout=5.0, no_auth=True,
        )
        base.update(kw)
        return Config(**base)
    return make
