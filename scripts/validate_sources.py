#!/usr/bin/env python3
"""Validate data/sources.json against its schema (structural, offline).

Checks the registry is well-formed: required fields, types, id format and uniqueness,
URL shape, and no unknown keys — so "add a framework = add one JSON object" is an
enforced contract, not a promise. With `--fetch`, also probes each URL (and mirror)
and reports HTTP status + content-type; fetching is off by default (politeness).

Usage:
  python scripts/validate_sources.py
  python scripts/validate_sources.py --fetch
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ALLOWED = {"id", "url", "public", "mirrors"}


def _is_url(v) -> bool:
    return isinstance(v, str) and v.startswith(("http://", "https://"))


def validate(sources) -> list[str]:
    errors: list[str] = []
    if not isinstance(sources, list):
        return ["top level must be a JSON array"]
    seen: dict[str, int] = {}
    for i, s in enumerate(sources):
        where = f"[{i}]"
        if not isinstance(s, dict):
            errors.append(f"{where}: not an object"); continue
        if isinstance(s.get("id"), str):
            where = f"[{i}] {s['id']}"
        for key in ("id", "url", "public"):
            if key not in s:
                errors.append(f"{where}: missing required key {key!r}")
        extra = set(s) - ALLOWED
        if extra:
            errors.append(f"{where}: unknown keys {sorted(extra)} (allowed: {sorted(ALLOWED)})")
        sid = s.get("id")
        if "id" in s:
            if not isinstance(sid, str) or not ID_RE.match(sid or ""):
                errors.append(f"{where}: id must match {ID_RE.pattern}")
            elif sid in seen:
                errors.append(f"{where}: duplicate id {sid!r} (first at [{seen[sid]}])")
            else:
                seen[sid] = i
        if "url" in s and not _is_url(s["url"]):
            errors.append(f"{where}: url must be an http(s) string")
        if "public" in s and not isinstance(s["public"], bool):
            errors.append(f"{where}: public must be a boolean")
        mirrors = s.get("mirrors")
        if mirrors is not None and (not isinstance(mirrors, list) or any(not _is_url(m) for m in mirrors)):
            errors.append(f"{where}: mirrors must be a list of http(s) strings")
    return errors


def _fetch(url: str):
    import urllib.request

    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "open-regulatory-corpus/validate"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.headers.get("Content-Type", "")
    except Exception as exc:
        return getattr(exc, "code", "ERR"), type(exc).__name__


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate the source registry.")
    ap.add_argument("--path", default="data/sources.json", help="registry path (default data/sources.json)")
    ap.add_argument("--fetch", action="store_true", help="also probe each URL (network; off by default)")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.is_absolute():
        path = ROOT / args.path
    sources = json.loads(path.read_text())

    schema_path = ROOT / "data/sources.schema.json"
    if schema_path.exists():
        json.loads(schema_path.read_text())  # must at least be valid JSON

    errors = validate(sources)
    public = sum(1 for s in sources if isinstance(s, dict) and s.get("public"))
    try:
        display = path.relative_to(ROOT)
    except ValueError:
        display = path
    total = len(sources) if isinstance(sources, list) else "?"
    print(f"{display}: {total} entries "
          f"({public} public, {len(sources) - public if isinstance(sources, list) else '?'} skipped)")

    if args.fetch:
        for s in sources:
            if not isinstance(s, dict) or not s.get("public"):
                continue
            for u in [s.get("url"), *s.get("mirrors", [])]:
                if u:
                    status, ct = _fetch(u)
                    print(f"  {s.get('id'):16} {status}  {ct}  {u}")

    if errors:
        print("\nINVALID:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("sources.json OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
