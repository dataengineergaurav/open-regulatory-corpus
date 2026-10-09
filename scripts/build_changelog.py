#!/usr/bin/env python3
"""Render a human-readable changelog from Bronze drift.

Consumes detect_drift's diff and writes a per-release changelog (Markdown + JSON) that
ships as a release asset. Offline — it only reads manifests, never re-fetches.

Usage:
  python scripts/build_changelog.py [--current <run>] [--previous <run>] [--out-dir data/silver]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import detect_drift as dd

ROOT = Path(__file__).resolve().parents[1]


def render_markdown(report: dict, generated: str) -> str:
    lines = [f"# Corpus changelog — {report['current']}", "",
             f"_vs `{report['previous']}` · generated {generated}_", ""]
    if not (report["added"] or report["removed"] or report["changed"]):
        lines.append("No document-level changes since the previous run.")
        return "\n".join(lines).rstrip() + "\n"
    if report["added"]:
        lines += [f"## Added ({len(report['added'])})", ""]
        lines += [f"- `{i}`" for i in report["added"]] + [""]
    if report["changed"]:
        lines += [f"## Changed ({len(report['changed'])})", "",
                  "_same framework, different bytes — re-ingested with a new `sha256_raw`_", ""]
        lines += [f"- `{i}`" for i in report["changed"]] + [""]
    if report["removed"]:
        lines += [f"## Removed ({len(report['removed'])})", ""]
        lines += [f"- `{i}`" for i in report["removed"]] + [""]
    n = report["unchanged"]
    lines.append(f"_{n} document{'s' if n != 1 else ''} unchanged._")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a changelog from Bronze drift.")
    ap.add_argument("--current", help="run id or path (default: newest run)")
    ap.add_argument("--previous", help="run id or path (default: the run before current)")
    ap.add_argument("--out-dir", default="data/silver", help="where to write changelog-<run>.md/.json")
    args = ap.parse_args()

    cur, prev = dd.resolve(args.current, args.previous)
    if cur is None:
        print("no Bronze runs found"); return 0
    if prev is None or not (prev / "manifest.jsonl").exists():
        print(f"current={cur.name}: no previous run to compare against"); return 0

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {"current": cur.name, "previous": prev.name, "generated": generated,
              **dd.diff(dd.load(cur), dd.load(prev))}
    md = render_markdown(report, generated)

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"changelog-{cur.name}.md").write_text(md)
    (out_dir / f"changelog-{cur.name}.json").write_text(json.dumps(report, indent=2))
    print(f"wrote changelog-{cur.name}.md/.json to {out_dir}")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
