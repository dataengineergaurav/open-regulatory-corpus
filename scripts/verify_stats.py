#!/usr/bin/env python3
"""Assert the corpus statistics CSVs agree with the artifacts they describe."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_stats as cs  # noqa: E402


def check() -> list[str]:
    """Return mismatches between the stats asset and the artifacts (empty = consistent)."""
    tables = cs.load()
    stats = tables["corpus_stats"][0]
    df = pq.read_table(str(ROOT / "data/silver/compliance_chunks.parquet")).to_pandas()
    stems = df.framework_id.astype(str).str.split("_pdf").str[0]
    manifest = [json.loads(l)
                for l in (ROOT / "data/bronze/latest/manifest.jsonl").read_text().splitlines() if l.strip()]

    errors: list[str] = []

    def expect(key: str, actual: int) -> None:
        if int(stats[key]) != int(actual):
            errors.append(f"{key}: csv={stats[key]} artifacts={actual}")

    expect("chunks", len(df))
    expect("docs", df.sha256.nunique())
    expect("frameworks_present", stems.nunique())
    expect("manifest_ok", sum(1 for r in manifest if r.get("status") == "ok"))
    expect("manifest_skipped", sum(1 for r in manifest if r.get("status") == "skipped_public_only"))
    expect("manifest_error", sum(1 for r in manifest if r.get("status") == "error"))

    present = {str(x) for x in stems}
    for g in tables.get("gaps", []):
        if g["id"] in present:
            errors.append(f"gaps: {g['id']} has chunks but is listed as a gap")
    return errors


def main() -> int:
    errors = check()
    for e in errors:
        print(f"  !! {e}")
    if errors:
        print(f"STATS INCONSISTENT ({len(errors)})")
        return 1
    print("STATS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
