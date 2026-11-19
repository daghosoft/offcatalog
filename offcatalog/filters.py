"""Filtri e pulizia dei prodotti. Un prodotto entra nel catalogo solo se passa tutti i controlli.

Colonne dell'export CSV di Open Food Facts usate (verificate sull'intestazione reale):
code, countries_tags, product_name, (product_name_it se presente), brands, energy-kcal_100g, energy-kj_100g,
energy_100g (kJ), fat_100g, saturated-fat_100g, carbohydrates_100g, sugars_100g, fiber_100g, proteins_100g,
salt_100g, sodium_100g, alcohol_100g, serving_size, serving_quantity, nutriscore_grade, nova_group,
last_modified_t.
"""
from __future__ import annotations

import re

from .config import Config

REASONS = ("paese", "barcode", "nome", "kcal", "coerenza", "doppione", "riga_malformata")
KJ_PER_KCAL = 4.184
BARCODE_RE = re.compile(r"^[0-9]{8,14}$")

NEEDED = (
    "code", "countries_tags", "product_name", "product_name_it", "brands", "energy-kcal_100g",
    "energy-kj_100g", "energy_100g", "fat_100g", "saturated-fat_100g", "carbohydrates_100g",
    "sugars_100g", "fiber_100g", "proteins_100g", "salt_100g", "sodium_100g", "alcohol_100g",
    "serving_size", "serving_quantity", "nutriscore_grade", "nova_group", "last_modified_t",
)


def num(s: str | None) -> float | None:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        v = float(s.replace(",", "."))
    except ValueError:
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def _pct_value(s: str | None) -> float | None:
    """Valore per 100 g: ammesso solo fra 0 e 100, altrimenti non noto."""
    v = num(s)
    if v is None or v < 0 or v > 100:
        return None
    return round(v, 2)


class RowFilter:
    """Applica i filtri a una riga (lista di campi) e restituisce (record | None, motivo | None)."""

    def __init__(self, header: list[str], cfg: Config):
        self.cfg = cfg
        self.countries = tuple(cfg.countries)
        self.idx = {name: header.index(name) for name in NEEDED if name in header}
        for required in ("code", "countries_tags", "product_name"):
            if required not in self.idx:
                raise ValueError(f"colonna mancante nell'export: {required}")
        self.ncols = len(header)

    def _get(self, row: list[str], name: str) -> str:
        i = self.idx.get(name)
        return row[i] if i is not None else ""

    def process(self, row: list[str]):
        g = self._get
        tags = [t.strip().lower() for t in g(row, "countries_tags").split(",")]
        if not any(c in tags for c in self.countries):
            return None, "paese"
        code = g(row, "code").strip()
        if not BARCODE_RE.match(code):
            return None, "barcode"
        name = g(row, "product_name_it").strip() or g(row, "product_name").strip()
        if not name:
            return None, "nome"

        kcal = num(g(row, "energy-kcal_100g"))
        if kcal is None:
            kj = num(g(row, "energy-kj_100g"))
            if kj is None:
                kj = num(g(row, "energy_100g"))
            if kj is not None:
                kcal = kj / KJ_PER_KCAL
        if kcal is None or kcal < self.cfg.kcal_min or kcal > self.cfg.kcal_max:
            return None, "kcal"
        kcal = round(kcal, 1)

        fat_raw, carbs_raw, prot_raw = (num(g(row, n)) for n in
                                        ("fat_100g", "carbohydrates_100g", "proteins_100g"))
        if None not in (fat_raw, carbs_raw, prot_raw):
            if any(v < 0 or v > 100 for v in (fat_raw, carbs_raw, prot_raw)):
                return None, "coerenza"
            alcohol = num(g(row, "alcohol_100g")) or 0.0
            calc = 9 * fat_raw + 4 * carbs_raw + 4 * prot_raw + 7 * max(alcohol, 0.0)
            tol = max(self.cfg.coherence_abs, self.cfg.coherence_pct * kcal)
            if abs(calc - kcal) > tol:
                return None, "coerenza"

        salt = _pct_value(g(row, "salt_100g"))
        if salt is None:
            sodium = num(g(row, "sodium_100g"))
            if sodium is not None and 0 <= sodium <= 40:
                salt = round(sodium * 2.5, 2)

        serving = num(g(row, "serving_quantity"))
        if serving is not None and not (0 < serving <= 5000):
            serving = None
        grade = g(row, "nutriscore_grade").strip().lower()
        nova = num(g(row, "nova_group"))
        lm = num(g(row, "last_modified_t"))
        brand = g(row, "brands").split(",")[0].strip()

        rec = (
            code, name, brand or None, kcal,
            _pct_value(g(row, "fat_100g")), _pct_value(g(row, "saturated-fat_100g")),
            _pct_value(g(row, "carbohydrates_100g")), _pct_value(g(row, "sugars_100g")),
            _pct_value(g(row, "fiber_100g")), _pct_value(g(row, "proteins_100g")), salt,
            g(row, "serving_size").strip() or None, serving,
            grade if grade in ("a", "b", "c", "d", "e") else None,
            int(nova) if nova in (1, 2, 3, 4) else None,
            int(lm) if lm is not None else None,
        )
        return rec, None
