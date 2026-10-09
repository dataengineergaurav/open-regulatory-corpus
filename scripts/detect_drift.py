#!/usr/bin/env python3
"""Drift detection: compare one Bronze run's documents against another.

By default it diffs the **extracted-text** hashes (`data/silver/index/<run>.json`,
written by build_silver) — a stable signal that ignores dynamic-page chrome. When a run
has no index, it falls back to the raw manifest hashes (`sha256_raw`), which is noisier
for live HTML. Offline — it never re-fetches.

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
INDEX_DIR = ROOT / "data/silver/index"


def runs() -> list[Path]:
    return sorted(p for p in BRONZE.glob("20*") if (p / "manifest.jsonl").exists())


def _load_manifest(run: Path) -> dict[str, dict]:
    """id -> sha256_raw, for every `ok` document in the run's manifest."""
    rows = [json.loads(l) for l in (run / "manifest.jsonl").read_text().splitlines() if l.strip()]
    return {str(r["id"]): {"sha256": r.get("sha256_raw")} for r in rows if r.get("status") == "ok"}


def _load_index(run: Path) -> dict[str, dict] | None:
    """id -> extracted-text sha256, if the run wrote an index; else None."""
    path = INDEX_DIR / f"{run.name}.json"
    if not path.exists():
        return None
    docs = json.loads(path.read_text()).get("docs", {})
    return {k: {"sha256": v["sha256"]} for k, v in docs.items()}


def load(run: Path) -> dict[str, dict]:
    """Documents for a run keyed by id (raw manifest hashes)."""
    return _load_manifest(run)


def diff(current: dict, previous: dict) -> dict:
    cur, prev = set(current), set(previous)
    changed = sorted(k for k in cur & prev if current[k]["sha256"] != previous[k]["sha256"])
    return {
        "added": sorted(cur - prev),
        "removed": sorted(prev - cur),
        "changed": changed,
        "unchanged": len(cur & prev) - len(changed),
    }


def compare(cur: Path, prev: Path) -> tuple[dict, str]:
    """Diff two runs, using extracted-text hashes when both runs have an index, else raw hashes."""
    ci, pi = _load_index(cur), _load_index(prev)
    if ci is not None and pi is not None:
        return diff(ci, pi), "extracted"
    return diff(_load_manifest(cur), _load_manifest(prev)), "raw"


def resolve(current: str | None = None, previous: str | None = None):
    """Resolve the (current, previous) run paths; previous is None if there's nothing to compare."""
    rs = runs()
    if not rs:
        return None, None
    cur = Path(current) if current else rs[-1]
    if not cur.is_absolute():
        cur = ROOT / cur
    if previous:
        prev = Path(previous)
        if not prev.is_absolute():
            prev = ROOT / previous
    else:
        names = [p.name for p in rs]
        idx = names.index(cur.name) if cur.name in names else len(rs) - 1
        prev = rs[idx - 1] if idx > 0 else None
    return cur, prev


def main() -> int:
    ap = argparse.ArgumentParser(description="Diff two Bronze runs by document hash.")
    ap.add_argument("--current", help="run id or path (default: newest run)")
    ap.add_argument("--previous", help="run id or path (default: the run before current)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a summary line")
    ap.add_argument("--out", help="also write the JSON report to this path")
    ap.add_argument("--fail-on-drift", action="store_true", help="exit 1 if anything changed")
    args = ap.parse_args()

    cur, prev = resolve(args.current, args.previous)
    if cur is None:
        print("no Bronze runs found"); return 0
    if not (cur / "manifest.jsonl").exists():
        print(f"current run has no manifest: {cur}"); return 0
    if prev is None or not (prev / "manifest.jsonl").exists():
        print(f"current={cur.name}: no previous run to compare against"); return 0

    d, signal = compare(cur, prev)
    d.update({"current": cur.name, "previous": prev.name, "signal": signal})
    drift = bool(d["added"] or d["removed"] or d["changed"])

    if args.json:
        print(json.dumps(d, indent=2))
    else:
        print(f"drift {prev.name} -> {cur.name} (by {signal}): {len(d['added'])} added · "
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
