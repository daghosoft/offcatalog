"""Configurazione da variabili d'ambiente (nessun segreto nel codice)."""
from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field, replace
from pathlib import Path

DEFAULT_SOURCE_URL = "https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz"
DEFAULT_API_ALLOW = "127.0.0.1,172.16.0.0/12"
OUTPUT_NAME = "off_catalog.db"


def _bool(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "si")


def parse_networks(text: str):
    nets = []
    for part in text.split(","):
        part = part.strip()
        if part:
            nets.append(ipaddress.ip_network(part, strict=False))
    return nets


@dataclass(frozen=True)
class Config:
    work_dir: Path
    output_dir: Path
    source_url: str = DEFAULT_SOURCE_URL
    countries: tuple = ("en:italy",)
    min_products: int = 100_000
    min_ratio: float = 0.80
    block_size: int = 5000
    kcal_min: float = 1.0
    kcal_max: float = 900.0
    coherence_pct: float = 0.35
    coherence_abs: float = 40.0
    api_allow: str = DEFAULT_API_ALLOW
    panel_user: str = ""
    panel_password: str = ""
    no_auth: bool = False
    keep_work: bool = False
    nice: int = 10
    http_timeout: float = 30.0
    download_retries: int = 5
    retry_base: float = 2.0
    runs_keep: int = 200

    @property
    def state_db(self) -> Path:
        return self.work_dir / "state.db"

    @property
    def lock_file(self) -> Path:
        return self.work_dir / "sync.lock"

    @property
    def build_db(self) -> Path:
        return self.work_dir / "build.db"

    @property
    def gz_part(self) -> Path:
        return self.work_dir / "export.csv.gz.part"

    @property
    def gz_file(self) -> Path:
        return self.work_dir / "export.csv.gz"

    @property
    def csv_file(self) -> Path:
        return self.work_dir / "export.csv"

    @property
    def csv_part(self) -> Path:
        return self.work_dir / "export.csv.part"

    @property
    def csv_ok(self) -> Path:
        return self.work_dir / "export.csv.ok"

    @property
    def download_info(self) -> Path:
        return self.work_dir / "download.json"

    @property
    def output_db(self) -> Path:
        return self.output_dir / OUTPUT_NAME

    def networks(self):
        return parse_networks(self.api_allow)

    def with_(self, **kw) -> "Config":
        return replace(self, **kw)

    def to_env(self) -> dict:
        """Variabili d'ambiente per il processo di sync (stessa configurazione del web)."""
        return {
            "OFFCAT_WORK_DIR": str(self.work_dir),
            "OFFCAT_OUTPUT_DIR": str(self.output_dir),
            "OFFCAT_SOURCE_URL": self.source_url,
            "OFFCAT_COUNTRIES": ",".join(self.countries),
            "OFFCAT_MIN_PRODUCTS": str(self.min_products),
            "OFFCAT_MIN_RATIO": str(self.min_ratio),
            "OFFCAT_BLOCK_SIZE": str(self.block_size),
            "OFFCAT_KCAL_MIN": str(self.kcal_min),
            "OFFCAT_KCAL_MAX": str(self.kcal_max),
            "OFFCAT_COHERENCE_PCT": str(self.coherence_pct),
            "OFFCAT_COHERENCE_ABS": str(self.coherence_abs),
            "OFFCAT_HTTP_TIMEOUT": str(self.http_timeout),
            "OFFCAT_DOWNLOAD_RETRIES": str(self.download_retries),
            "OFFCAT_RETRY_BASE": str(self.retry_base),
            "OFFCAT_KEEP_WORK": "1" if self.keep_work else "0",
            "OFFCAT_NICE": str(self.nice),
        }

    @staticmethod
    def from_env(env=None) -> "Config":
        e = os.environ if env is None else env
        countries = tuple(
            c.strip().lower() for c in e.get("OFFCAT_COUNTRIES", "en:italy").split(",") if c.strip()
        )
        return Config(
            work_dir=Path(e.get("OFFCAT_WORK_DIR", "./work")),
            output_dir=Path(e.get("OFFCAT_OUTPUT_DIR", "./output")),
            source_url=e.get("OFFCAT_SOURCE_URL", DEFAULT_SOURCE_URL),
            countries=countries or ("en:italy",),
            min_products=int(e.get("OFFCAT_MIN_PRODUCTS", "100000")),
            min_ratio=float(e.get("OFFCAT_MIN_RATIO", "0.80")),
            block_size=int(e.get("OFFCAT_BLOCK_SIZE", "5000")),
            kcal_min=float(e.get("OFFCAT_KCAL_MIN", "1")),
            kcal_max=float(e.get("OFFCAT_KCAL_MAX", "900")),
            coherence_pct=float(e.get("OFFCAT_COHERENCE_PCT", "0.35")),
            coherence_abs=float(e.get("OFFCAT_COHERENCE_ABS", "40")),
            http_timeout=float(e.get("OFFCAT_HTTP_TIMEOUT", "30")),
            download_retries=int(e.get("OFFCAT_DOWNLOAD_RETRIES", "5")),
            retry_base=float(e.get("OFFCAT_RETRY_BASE", "2")),
            api_allow=e.get("OFFCAT_API_ALLOW", DEFAULT_API_ALLOW),
            panel_user=e.get("OFFCAT_PANEL_USER", ""),
            panel_password=e.get("OFFCAT_PANEL_PASSWORD", ""),
            no_auth=_bool(e.get("OFFCAT_NO_AUTH")),
            keep_work=_bool(e.get("OFFCAT_KEEP_WORK")),
            nice=int(e.get("OFFCAT_NICE", "10")),
        )
