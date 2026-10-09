#!/usr/bin/env python3
"""Acquisition health: does every public source actually yield usable text?

Cross-references data/sources.json, the Bronze manifest, and the Silver chunks. The
Bronze verifier can pass while a source is a JavaScript shell or WAF page ("ok" but
extractable to noise); this check surfaces those silent gaps, plus errored sources.

Usage:
  python scripts/verify_sources.py            # report; exit 0
  python scripts/verify_sources.py --strict   # exit 1 if any public source is not healthy
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_sources() -> list[dict]:
    return json.loads((ROOT / "data/sources.json").read_text())


def load_manifest() -> tuple[dict[str, list[dict]], str]:
    bronze = ROOT / "data/bronze" / "latest"
    if not bronze.exists():
        candidates = sorted((ROOT / "data/bronze").glob("20*"), reverse=True)
        bronze = candidates[0] if candidates else None
    if bronze is None:
        return {}, "none"
    rows = [json.loads(l) for l in (bronze / "manifest.jsonl").read_text().splitlines() if l.strip()]
    by_id: dict[str, list[dict]] = {}
    for r in rows:
        rid = str(r.get("id", ""))
        base = rid.split("_pdf")[0]
        by_id.setdefault(base, []).append(r)
    return by_id, bronze.name


def load_chunks() -> dict[str, int] | None:
    parquet = ROOT / "data/silver/compliance_chunks.parquet"
    if not parquet.exists():
        return None
    try:
        import pandas as pd

        df = pd.read_parquet(parquet)
    except Exception:
        try:
            import pyarrow.parquet as pq

            df = pq.read_table(str(parquet)).to_pandas()
        except Exception:
            return None
    stems = df.framework_id.astype(str).str.split("_pdf").str[0]
    return {str(k): int(v) for k, v in stems.value_counts().to_dict().items()}


def main() -> int:
    ap = argparse.ArgumentParser(description="Report per-source acquisition health.")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any public source is not healthy")
    args = ap.parse_args()

    sources = load_sources()
    manifest, run = load_manifest()
    chunks = load_chunks()
    public = [s for s in sources if s.get("public")]

    print(f"acquisition health — run `{run}`, {len(public)} public sources\n")
    print(f"{'source':16} {'mirrors':7} {'manifest':8} {'chunks':>6}  verdict")
    print("-" * 60)

    unhealthy: list[str] = []
    counts: dict[str, int] = {}
    for s in public:
        sid = s["id"]
        rows = manifest.get(sid, [])
        status = "-"
        for r in rows:
            if r.get("id") == sid:
                status = r.get("status", "?")
                break
        has_primary = any(r.get("id") == sid for r in rows)
        if status == "-" and rows and not has_primary:
            status = rows[0].get("status", "?")
        n = (chunks or {}).get(sid, 0)
        if n > 0:
            verdict = "healthy"
        elif status == "error":
            verdict = "ERROR (unfetched)"
        elif status == "ok":
            verdict = "EMPTY (ok, 0 chunks)"
        else:
            verdict = status
        counts[verdict] = counts.get(verdict, 0) + 1
        if verdict != "healthy":
            unhealthy.append(sid)
        print(f"{sid:16} {len(s.get('mirrors', [])):7} {status:8} {n:>6}  {verdict}")

    print("-" * 60)
    for v, c in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {c:3}  {v}")

    if unhealthy:
        print(f"\nnot healthy ({len(unhealthy)}): " + ", ".join(unhealthy))

    if args.strict and unhealthy:
        print("\nSTRICT: acquisition is not fully healthy (see above).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
