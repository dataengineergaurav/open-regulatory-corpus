#!/usr/bin/env python3
"""Read the corpus statistics asset (`data/stats/*.csv`) and present it.

Reader/presenter half of the stats asset. Stdlib-only by design so it runs anywhere,
including Colab and the docs tooling. The writer half is `build_stats.py`.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "stats"

# Scalar columns that need a format other than the default (thousands-separated int).
FORMATS = {"run_id": "str", "tokens": "tokens", "raw_mib": "mib", "top3_share": "pct"}


def _fmt(kind: str, raw: str) -> str:
    if kind == "str":
        return str(raw)
    if kind == "tokens":
        return f"~{int(raw):,}"
    if kind == "mib":
        return f"{int(raw)} MB"
    if kind == "pct":
        return f"~{round(float(raw) * 100)}%"
    return f"{int(raw):,}"


def load() -> dict[str, list[dict]]:
    """Every CSV in the asset, keyed by file stem. A missing directory raises."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(DATA_DIR)
    tables: dict[str, list[dict]] = {}
    for path in sorted(DATA_DIR.glob("*.csv")):
        with path.open(newline="") as f:
            tables[path.stem] = list(csv.DictReader(f))
    return tables


def values() -> dict[str, str]:
    """The scalar `corpus_stats` row as a `column -> formatted string` map."""
    row = load()["corpus_stats"][0]
    return {k: _fmt(FORMATS.get(k, "int"), v) for k, v in row.items()}
