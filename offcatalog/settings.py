"""Impostazioni modificabili dal pannello: validazione, conversione e Config effettiva.

Precedenza: valore salvato dal pannello (tabella `settings` di state.db) > variabile d'ambiente > default del codice.
Solo le chiavi di FIELDS sono modificabili; tutto il resto resta solo da variabili d'ambiente.
"""
from __future__ import annotations

import math
import re

from .config import Config

COUNTRY_RE = re.compile(r"^[a-z0-9_-]+:[a-z0-9_-]+$")
KCAL_MAX_LIMITE = 2000

# ordine di visualizzazione; "tipo": testo | numero | intero | bool
FIELDS = {
    "countries": {
        "tipo": "testo", "etichetta": "Paesi",
        "descrizione": "Paesi da tenere, separati da virgola (formato en:italy). Un prodotto entra se e' "
                       "venduto in almeno uno di questi paesi.",
    },
    "kcal_min": {
        "tipo": "numero", "etichetta": "Calorie minime (per 100 g)",
        "descrizione": "Scarta i prodotti con meno calorie di questa soglia.",
    },
    "kcal_max": {
        "tipo": "numero", "etichetta": "Calorie massime (per 100 g)",
        "descrizione": f"Scarta i prodotti con piu' calorie di questa soglia (al massimo {KCAL_MAX_LIMITE}).",
    },
    "coherence_pct": {
        "tipo": "numero", "etichetta": "Tolleranza coerenza (frazione)",
        "descrizione": "Quanto possono differire le calorie dichiarate da quelle calcolate da grassi, "
                       "carboidrati e proteine, come frazione delle calorie (da 0 a 1; 0,35 = 35%).",
    },
    "coherence_abs": {
        "tipo": "numero", "etichetta": "Tolleranza coerenza minima (kcal)",
        "descrizione": "Tolleranza minima assoluta in kcal: vale la piu' grande fra questa e la frazione.",
    },
    "min_products": {
        "tipo": "intero", "etichetta": "Prodotti minimi",
        "descrizione": "Controllo prima di pubblicare: se il catalogo ha meno prodotti, non viene pubblicato.",
    },
    "min_ratio": {
        "tipo": "numero", "etichetta": "Rapporto minimo col pubblicato",
        "descrizione": "Controllo prima di pubblicare: il nuovo catalogo deve avere almeno questa frazione "
                       "dei prodotti di quello pubblicato (da 0 a 1).",
    },
    "keep_work": {
        "tipo": "bool", "etichetta": "Conserva i file di lavoro",
        "descrizione": "Dopo la pubblicazione non cancella CSV e catalogo di lavoro (utile per diagnosi, "
                       "occupa molto spazio).",
    },
}
KEYS = tuple(FIELDS)
# chiavi che finiscono nella tabella meta del catalogo (countries c'e' gia' come `countries`)
META_KEYS = tuple(k for k in KEYS if k != "countries")


def _number(raw, key: str) -> float:
    if isinstance(raw, bool):
        raise ValueError("deve essere un numero")
    if isinstance(raw, (int, float)):
        v = float(raw)
    elif isinstance(raw, str):
        try:
            v = float(raw.strip().replace(",", "."))
        except ValueError:
            raise ValueError("deve essere un numero") from None
    else:
        raise ValueError("deve essere un numero")
    if not math.isfinite(v):
        raise ValueError("deve essere un numero finito")
    return v


def parse_value(key: str, raw):
    """Converte e controlla un singolo campo. ValueError con messaggio in italiano."""
    if key not in FIELDS:
        raise ValueError("impostazione non modificabile")
    tipo = FIELDS[key]["tipo"]
    if key == "countries":
        if isinstance(raw, str):
            items = [c.strip().lower() for c in raw.split(",")]
        elif isinstance(raw, (list, tuple)) and all(isinstance(c, str) for c in raw):
            items = [c.strip().lower() for c in raw]
        else:
            raise ValueError("deve essere un elenco di paesi separati da virgola")
        items = [c for c in items if c]
        if not items:
            raise ValueError("indica almeno un paese")
        bad = [c for c in items if not COUNTRY_RE.match(c)]
        if bad:
            raise ValueError(f"formato non valido ({bad[0]}): usa xx:nome, minuscolo, es. en:italy")
        out = []
        for c in items:
            if c not in out:
                out.append(c)
        return tuple(out)
    if tipo == "bool":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str) and raw.strip().lower() in ("1", "true", "yes", "si", "0", "false", "no"):
            return raw.strip().lower() in ("1", "true", "yes", "si")
        raise ValueError("deve essere vero o falso")
    v = _number(raw, key)
    if tipo == "intero":
        if v != int(v):
            raise ValueError("deve essere un numero intero")
        v = int(v)
        if v < 0:
            raise ValueError("deve essere almeno 0")
        return v
    if key == "kcal_min" and v < 0:
        raise ValueError("deve essere almeno 0")
    if key == "kcal_max" and v > KCAL_MAX_LIMITE:
        raise ValueError(f"al massimo {KCAL_MAX_LIMITE}")
    if key == "coherence_abs" and v < 0:
        raise ValueError("deve essere almeno 0")
    if key in ("coherence_pct", "min_ratio") and not 0 <= v <= 1:
        raise ValueError("deve essere fra 0 e 1")
    return v


def cross_check(values: dict) -> dict:
    """Controlli fra campi, sull'insieme dei valori effettivi. Restituisce {chiave: messaggio}."""
    errs = {}
    if values["kcal_max"] <= values["kcal_min"]:
        errs["kcal_max"] = "deve essere maggiore delle calorie minime"
    return errs


def to_text(key: str, value) -> str:
    if key == "countries":
        return ",".join(value)
    if FIELDS[key]["tipo"] == "bool":
        return "1" if value else "0"
    return str(value)


def values_of(cfg: Config) -> dict:
    return {k: getattr(cfg, k) for k in KEYS}


def apply_overrides(base: Config, stored: dict) -> Config:
    """Config effettiva: env/default (base) + valori salvati. Valori salvati non validi sono ignorati."""
    kw = {}
    for k, text in stored.items():
        if k not in FIELDS:
            continue
        try:
            kw[k] = parse_value(k, text)
        except ValueError:
            continue
    merged = {**values_of(base), **kw}
    if cross_check(merged):
        kw.pop("kcal_min", None)
        kw.pop("kcal_max", None)
    return base.with_(**kw) if kw else base


def effective_dict(cfg: Config) -> dict:
    """Impostazioni in forma JSON (liste e numeri semplici), per report e meta."""
    out = {}
    for k in KEYS:
        v = getattr(cfg, k)
        out[k] = list(v) if k == "countries" else v
    return out
