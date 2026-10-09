#!/usr/bin/env python3
"""Generate the corpus statistics CSV family from the artifacts (the stats asset).

Writer half of the asset: reads `data/sources.json` + the newest Bronze manifest + the
Silver parquet and emits five wide CSVs under `data/stats/`. The reader/presenter half
lives in `corpus_stats.py`.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
STATS_DIR = ROOT / "data" / "stats"

DOMAINS = {
    "AI Governance": ["NIST-AI-RMF", "NIST-AI-600-1", "EU-AI-ACT", "OMB-M25-21", "OMB-M25-22",
                      "OWASP-LLM-2026", "CO-AI", "TX-TRAIGA", "SG-MODEL-AI"],
    "Privacy & Data": ["GDPR", "CCPA-CPRA", "FERPA", "COPPA", "UK-DP-AI", "BR-LGPD",
                       "AU-PRIVACY-AI", "DOJ-DSP"],
    "Cybersecurity": ["NIST-CSF2", "NIST-800-53", "NIST-800-171", "FEDRAMP", "CMMC",
                      "CJIS-6.1", "IRS-1075"],
    "Financial": ["SOX", "GLBA", "NYDFS-500", "FRB-MRM-2026", "ECOA-REG-B", "NAIC-AI"],
    "Health/Access/Trade": ["HIPAA", "HHS-PART2", "SECTION-508", "ONC-HTI1", "FDA-AI-MD",
                            "NYC-LL144", "IL-AIVIA", "EAR"],
}

COLUMNS = {
    "corpus_stats": ["run_id", "chunks", "docs", "frameworks_present", "frameworks_total",
                     "tokens", "chunk_pdf", "chunk_html", "median_words", "raw_files",
                     "raw_pdf", "raw_html", "raw_mib", "manifest_ok", "manifest_skipped",
                     "manifest_error", "sources_total", "sources_public", "sources_skipped",
                     "top3_share"],
    "gaps": ["id", "cause"],
    "domains": ["domain", "chunks"],
    "top_documents": ["framework_id", "chunks"],
    "paywalled": ["id"],
}


def _manifest() -> list[dict]:
    bronze = ROOT / "data/bronze/latest"
    if not bronze.exists():
        candidates = sorted((ROOT / "data/bronze").glob("20*"), reverse=True)
        bronze = candidates[0] if candidates else None
    if bronze is None:
        return []
    return [json.loads(l) for l in (bronze / "manifest.jsonl").read_text().splitlines() if l.strip()]


def _cause(status: str) -> str:
    return ("The server returned a non-200 response" if status == "error"
            else "Served a shell / wrapper page (filtered at the Silver stage)")


def collect() -> dict[str, list[dict]]:
    sources = json.loads((ROOT / "data/sources.json").read_text())
    manifest = _manifest()
    df = pq.read_table(str(ROOT / "data/silver/compliance_chunks.parquet")).to_pandas()
    stems = df.framework_id.astype(str).str.split("_pdf").str[0]

    ok = [r for r in manifest if r.get("status") == "ok"]
    pdfs = sum(1 for r in ok if "pdf" in (r.get("content_type") or "").lower())
    raw_bytes = sum(r.get("bytes", 0) for r in ok)
    kinds = df.kind.value_counts().to_dict()
    top = stems.value_counts()
    public_ids = [s["id"] for s in sources if s.get("public")]
    status_by_id: dict[str, str] = {}
    for r in manifest:
        status_by_id.setdefault(str(r.get("id", "")).split("_pdf")[0], str(r.get("status")))
    present = {str(x) for x in stems}
    gap_ids = sorted(i for i in public_ids if i not in present)
    top3 = int(top.head(3).sum())

    stats_row = {
        "run_id": os.path.basename(os.path.realpath(ROOT / "data/bronze/latest")),
        "chunks": int(len(df)),
        "docs": int(df.sha256.nunique()),
        "frameworks_present": int(stems.nunique()),
        "frameworks_total": len(public_ids),
        "tokens": int(df.token_est.sum()),
        "chunk_pdf": int(kinds.get("pdf", 0)),
        "chunk_html": int(kinds.get("html", 0)),
        "median_words": int(df.text.str.split().str.len().median()),
        "raw_files": len(ok),
        "raw_pdf": pdfs,
        "raw_html": len(ok) - pdfs,
        "raw_mib": round(raw_bytes / 1024 / 1024),
        "manifest_ok": len(ok),
        "manifest_skipped": sum(1 for r in manifest if r.get("status") == "skipped_public_only"),
        "manifest_error": sum(1 for r in manifest if r.get("status") == "error"),
        "sources_total": len(sources),
        "sources_public": len(public_ids),
        "sources_skipped": len(sources) - len(public_ids),
        "top3_share": round(top3 / len(df), 3) if len(df) else 0.0,
    }

    return {
        "corpus_stats": [{k: stats_row[k] for k in COLUMNS["corpus_stats"]}],
        "gaps": [{"id": i, "cause": _cause(status_by_id.get(i, "missing"))} for i in gap_ids],
        "domains": [{"domain": d, "chunks": int(stems.isin(ids).sum())} for d, ids in DOMAINS.items()],
        "top_documents": [{"framework_id": str(k), "chunks": int(v)}
                          for k, v in sorted(top.items(), key=lambda kv: (-kv[1], str(kv[0])))],
        "paywalled": [{"id": s["id"]} for s in sources if not s.get("public")],
    }


def write(stats_dir: Path) -> None:
    stats_dir = Path(stats_dir)
    stats_dir.mkdir(parents=True, exist_ok=True)
    data = collect()
    for name, cols in COLUMNS.items():
        with (stats_dir / f"{name}.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(data[name])


def main() -> int:
    write(STATS_DIR)
    print(f"wrote {len(COLUMNS)} CSVs to {STATS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
