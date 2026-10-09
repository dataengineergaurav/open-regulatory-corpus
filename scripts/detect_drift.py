#!/usr/bin/env python3
"""Drift detection: compare one Bronze run's documents against another, by raw hash.

Reads two `manifest.jsonl` files and reports which documents were added, removed, or
changed (same id, different `sha256_raw`). Purely offline — it diffs manifests, never
re-fetches. This is the signal the corpus otherwise loses: a document that changed
without a version bump re-ingests silently.

Usage:
  python scripts/detect_drift.py                    # newest run vs the one before it
  python scripts/detect_drift.py --current <run> --previous <run>
  python scripts/detect_drift.py --json [--out data/silver/drift_report.json]
  python scripts/detect_drift.py --fail-on-drift    # exit 1 if anything drifted
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRONZE = ROOT / "data/bronze"


def runs() -> list[Path]:
    return sorted(p for p in BRONZE.glob("20*") if (p / "manifest.jsonl").exists())


def load(run: Path) -> dict[str, dict]:
    rows = [json.loads(l) for l in (run / "manifest.jsonl").read_text().splitlines() if l.strip()]
    docs: dict[str, dict] = {}
    for r in rows:
        if r.get("status") != "ok":
            continue
        docs[str(r.get("id"))] = {
            "sha256": r.get("sha256_raw"),
            "url": r.get("url"),
            "bytes": r.get("bytes"),
        }
    return docs


def diff(current: dict, previous: dict) -> dict:
    cur, prev = set(current), set(previous)
    changed = sorted(k for k in cur & prev if current[k]["sha256"] != previous[k]["sha256"])
    return {
        "added": sorted(cur - prev),
        "removed": sorted(prev - cur),
        "changed": changed,
        "unchanged": len(cur & prev) - len(changed),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Diff two Bronze runs by raw document hash.")
    ap.add_argument("--current", help="run id or path (default: newest run)")
    ap.add_argument("--previous", help="run id or path (default: the run before current)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a summary line")
    ap.add_argument("--out", help="also write the JSON report to this path")
    ap.add_argument("--fail-on-drift", action="store_true", help="exit 1 if anything changed")
    args = ap.parse_args()

    rs = runs()
    if not rs:
        print("no Bronze runs found"); return 0

    cur = Path(args.current) if args.current else rs[-1]
    if not cur.is_absolute():
        cur = ROOT / cur
    if not (cur / "manifest.jsonl").exists():
        print(f"current run has no manifest: {cur}"); return 0

    if args.previous:
        prev = Path(args.previous)
        if not prev.is_absolute():
            prev = ROOT / prev
    else:
        names = [p.name for p in rs]
        idx = names.index(cur.name) if cur.name in names else len(rs) - 1
        prev = rs[idx - 1] if idx > 0 else None

    if prev is None or not (prev / "manifest.jsonl").exists():
        print(f"current={cur.name}: no previous run to compare against"); return 0

    d = diff(load(cur), load(prev))
    d.update({"current": cur.name, "previous": prev.name})
    drift = bool(d["added"] or d["removed"] or d["changed"])

    if args.json:
        print(json.dumps(d, indent=2))
    else:
        print(f"drift {prev.name} -> {cur.name}: {len(d['added'])} added · "
              f"{len(d['removed'])} removed · {len(d['changed'])} changed · {d['unchanged']} unchanged")
        for key in ("added", "removed", "changed"):
            if d[key]:
                print(f"  {key}: " + ", ".join(d[key]))
        if not drift:
            print("  no drift")

    if args.out:
        Path(args.out).write_text(json.dumps(d, indent=2))
    return 1 if (args.fail_on_drift and drift) else 0


if __name__ == "__main__":
    sys.exit(main())
