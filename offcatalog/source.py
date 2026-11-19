"""Sorgente: richiesta HEAD, download con ripresa HTTP Range, decompressione."""
from __future__ import annotations

import gzip
import json
import os
import time
import urllib.error
import urllib.request

from .config import Config

CHUNK = 1024 * 1024


class SourceChanged(Exception):
    pass


def head(cfg: Config) -> dict:
    """Informazioni sull'export. Solleva OSError/URLError se la sorgente non risponde."""
    req = urllib.request.Request(cfg.source_url, method="HEAD", headers={"User-Agent": "offcatalog"})
    with urllib.request.urlopen(req, timeout=cfg.http_timeout) as r:
        size = r.headers.get("Content-Length")
        return {
            "url": cfg.source_url,
            "etag": r.headers.get("ETag"),
            "last_modified": r.headers.get("Last-Modified"),
            "size": int(size) if size and size.isdigit() else None,
        }


def head_safe(cfg: Config) -> dict:
    try:
        return head(cfg)
    except Exception:  # sorgente non raggiungibile: la sync fallira' con un messaggio chiaro
        return {"url": cfg.source_url, "etag": None, "last_modified": None, "size": None}


def same_source(a: dict, b: dict) -> bool:
    if not a or not b:
        return False
    if a.get("etag") and b.get("etag"):
        return a["etag"] == b["etag"]
    if a.get("last_modified") and b.get("last_modified"):
        return a["last_modified"] == b["last_modified"] and a.get("size") == b.get("size")
    return False


def _read_info(cfg: Config) -> dict:
    try:
        return json.loads(cfg.download_info.read_text())
    except (OSError, ValueError):
        return {}


def _remove(*paths):
    for p in paths:
        try:
            os.remove(p)
        except FileNotFoundError:
            pass


def download(cfg: Config, src: dict, ctl) -> None:
    """Scarica l'export in export.csv.gz, riprendendo da export.csv.gz.part se la sorgente non e' cambiata."""
    info = _read_info(cfg)
    if info and not same_source(info, src):
        ctl.log("sorgente cambiata: scarto il download precedente")
        _remove(cfg.gz_part, cfg.gz_file, cfg.csv_file, cfg.csv_ok)
        info = {}
    cfg.download_info.write_text(json.dumps(src))

    total = src.get("size")
    if cfg.gz_file.exists() and (total is None or cfg.gz_file.stat().st_size == total):
        ctl.progress(bytes_downloaded=cfg.gz_file.stat().st_size, bytes_total=total, speed=0)
        ctl.log("download gia' completo, riuso")
        return
    _remove(cfg.gz_file)

    attempts = 0
    while True:
        try:
            _download_once(cfg, src, ctl)
            break
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
            attempts += 1
            if attempts > cfg.download_retries:
                raise
            ctl.log(f"download interrotto ({e}), nuovo tentativo {attempts}/{cfg.download_retries}")
            ctl.check_stop()
            time.sleep(min(cfg.retry_base ** attempts, 30))
    os.replace(cfg.gz_part, cfg.gz_file)


def _download_once(cfg: Config, src: dict, ctl) -> None:
    have = cfg.gz_part.stat().st_size if cfg.gz_part.exists() else 0
    total = src.get("size")
    if total is not None and have > total:
        _remove(cfg.gz_part)
        have = 0
    if total is not None and have == total:
        return
    headers = {"User-Agent": "offcatalog"}
    if have:
        headers["Range"] = f"bytes={have}-"
        if src.get("etag"):
            headers["If-Range"] = src["etag"]
    req = urllib.request.Request(cfg.source_url, headers=headers)
    try:
        resp = urllib.request.urlopen(req, timeout=cfg.http_timeout)
    except urllib.error.HTTPError as e:
        if e.code == 416:  # parte gia' completa o fuori misura: si riparte da zero
            _remove(cfg.gz_part)
            raise OSError("range non soddisfacibile, riparto da zero")
        raise
    with resp:
        if have and resp.status == 200:
            have = 0  # il server ha ignorato Range (o il file e' cambiato): si riscrive da capo
        elif have and resp.status == 206:
            cr = resp.headers.get("Content-Range", "")
            if not cr.startswith(f"bytes {have}-"):
                raise OSError("Content-Range inatteso")
        etag = resp.headers.get("ETag")
        if src.get("etag") and etag and etag != src["etag"]:
            _remove(cfg.gz_part)
            raise SourceChanged("l'export e' cambiato durante il download")
        mode = "ab" if have else "wb"
        last = time.time()
        last_bytes = have
        with open(cfg.gz_part, mode) as out:
            while True:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                have += len(chunk)
                now = time.time()
                if now - last >= 1.0:
                    ctl.progress(
                        bytes_downloaded=have, bytes_total=total,
                        speed=(have - last_bytes) / (now - last),
                    )
                    last, last_bytes = now, have
                    ctl.check_stop()
                else:
                    ctl.check_stop_cheap()
    if total is not None and have != total:
        raise OSError(f"download incompleto: {have} di {total} byte")
    ctl.progress(bytes_downloaded=have, bytes_total=total, speed=0)


def decompress(cfg: Config, src: dict, ctl) -> None:
    """export.csv.gz -> export.csv (marcato da export.csv.ok con l'ETag della sorgente)."""
    if cfg.csv_file.exists() and cfg.csv_ok.exists():
        try:
            ok = json.loads(cfg.csv_ok.read_text())
        except ValueError:
            ok = {}
        if same_source(ok, src) or (not src.get("etag") and ok.get("last_modified") == src.get("last_modified")):
            ctl.progress(csv_bytes=cfg.csv_file.stat().st_size)
            ctl.log("CSV gia' decompresso, riuso")
            return
    _remove(cfg.csv_file, cfg.csv_ok, cfg.csv_part)
    gz_size = cfg.gz_file.stat().st_size
    last = time.time()
    with open(cfg.gz_file, "rb") as raw, gzip.GzipFile(fileobj=raw) as gz, open(cfg.csv_part, "wb") as out:
        while True:
            chunk = gz.read(4 * CHUNK)
            if not chunk:
                break
            out.write(chunk)
            now = time.time()
            if now - last >= 1.0:
                ctl.progress(decompress_pct=100.0 * raw.tell() / max(gz_size, 1),
                             csv_bytes=out.tell())
                last = now
                ctl.check_stop()
    os.replace(cfg.csv_part, cfg.csv_file)
    cfg.csv_ok.write_text(json.dumps(src))
    ctl.progress(decompress_pct=100.0, csv_bytes=cfg.csv_file.stat().st_size)
