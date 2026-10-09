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

# The asset is complete only when every one of these files is present.
EXPECTED = ("corpus_stats", "gaps", "domains", "top_documents", "paywalled")


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
    """Every CSV in the asset, keyed by file stem. A missing directory or file raises."""
    if not DATA_DIR.exists():
        raise FileNotFoundError(DATA_DIR)
    tables: dict[str, list[dict]] = {}
    for path in sorted(DATA_DIR.glob("*.csv")):
        with path.open(newline="") as f:
            tables[path.stem] = list(csv.DictReader(f))
    missing = [name for name in EXPECTED if name not in tables]
    if missing:
        raise FileNotFoundError(f"stats asset incomplete, missing: {missing}")
    return tables


def values() -> dict[str, str]:
    """The scalar `corpus_stats` row as a `column -> formatted string` map."""
    row = load()["corpus_stats"][0]
    return {k: _fmt(FORMATS.get(k, "int"), v) for k, v in row.items()}


def headline() -> str:
    v = values()
    return (f"{v['sources_public']} public frameworks → {v['raw_files']} raw documents "
            f"({v['raw_mib']}) → **{v['chunks']}** citation-ready chunks across "
            f"**{v['docs']}** documents")


def stats_bullets() -> str:
    v = values()
    top = ", ".join(f"**{r['framework_id']}** ({int(r['chunks']):,})"
                    for r in load()["top_documents"][:4])
    return (
        f"Measured from `data/silver/compliance_chunks.parquet` (run `{v['run_id']}`):\n\n"
        f"- **{v['chunks']}** chunks across **{v['docs']}** documents, spanning "
        f"**{v['frameworks_present']} of {v['sources_public']}** public frameworks\n"
        f"- **{v['tokens']}** estimated tokens of compliance text\n"
        f"- **{v['chunk_pdf']}** PDF chunks / **{v['chunk_html']}** HTML chunks\n"
        f"- **{v['median_words']}**-word median chunk length\n"
        f"- Largest documents: {top}\n"
        f"- Bronze: **{v['raw_files']}** raw files (**{v['raw_pdf']}** PDF · "
        f"**{v['raw_html']}** HTML, **{v['raw_mib']}**); manifest **{v['manifest_ok']}** ok · "
        f"**{v['manifest_skipped']}** skipped · **{v['manifest_error']}** error"
    )


def gaps_table() -> str:
    rows = load().get("gaps", [])
    groups: dict[str, list[str]] = {}
    for r in sorted(rows, key=lambda r: (r["cause"], r["id"])):
        groups.setdefault(r["cause"], []).append(r["id"])
    body = "\n".join(f"| {', '.join('`' + i + '`' for i in ids)} | {cause} |"
                     for cause, ids in groups.items())
    return (f"**{len(rows)}** of the {values()['frameworks_total']} public frameworks currently "
            f"produce **zero chunks**:\n\n| Framework | Why it's empty |\n|---|---|\n{body}")


def domains_table() -> str:
    body = "\n".join(f"| {r['domain']} | {int(r['chunks']):,} |" for r in load().get("domains", []))
    return f"| Domain | Chunks |\n|---|---|\n{body}"


def top_documents() -> str:
    body = "\n".join(f"| `{r['framework_id']}` | {int(r['chunks']):,} |"
                     for r in load().get("top_documents", [])[:4])
    return f"| Framework | Chunks |\n|---|---|\n{body}"


RENDERERS = {
    "headline": headline,
    "stats_bullets": stats_bullets,
    "gaps_table": gaps_table,
    "domains_table": domains_table,
    "top_documents": top_documents,
}

