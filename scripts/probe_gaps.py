#!/usr/bin/env python3
"""Probe the open gaps: does a zero-chunk framework now serve usable text?

For each public source that currently yields 0 chunks, politely fetch its `url` and
`mirrors` (robots.txt respected), extract, and report whether it now looks usable —
so a gap that opens up is noticed, not missed. Read-only: it never writes to data/ or
Bronze. This is the engine behind the weekly gap-watch workflow.

Usage:
  python scripts/probe_gaps.py [--min-chars 1000] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_sources as vs  # noqa: E402  (reuse its loaders)

UA = "open-regulatory-corpus/gapwatch (+https://github.com/dataengineergaurav/open-regulatory-corpus)"
MIN_CHARS = 1000
_rp_cache: dict[str, robotparser.RobotFileParser | None] = {}


def allowed(url: str) -> bool:
    host = urlparse(url).netloc
    if host not in _rp_cache:
        rp = robotparser.RobotFileParser()
        rp.set_url(f"https://{host}/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None
        _rp_cache[host] = rp
    rp = _rp_cache[host]
    return True if rp is None else rp.can_fetch(UA, url)


def fetch(url: str, timeout: int = 30):
    with urlopen(Request(url, headers={"User-Agent": UA}), timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def extract(body: bytes, content_type: str) -> str:
    if body[:4] == b"%PDF" or "pdf" in (content_type or "").lower():
        import fitz

        return "\n".join(p.get_text() for p in fitz.open(stream=body, filetype="pdf"))
    import trafilatura

    return trafilatura.extract(body.decode(errors="ignore"), include_comments=False) or ""


def is_usable(body: bytes, content_type: str, min_chars: int = MIN_CHARS, extractor=extract):
    try:
        text = (extractor(body, content_type) or "").strip()
    except Exception:
        return False, 0
    return len(text) >= min_chars, len(text)


def open_gaps() -> list[dict]:
    sources = vs.load_sources()
    chunks = vs.load_chunks() or {}
    return [s for s in sources if s.get("public") and chunks.get(s["id"], 0) == 0]


def probe(fetcher=fetch, min_chars: int = MIN_CHARS, extractor=extract) -> list[dict]:
    results = []
    for s in open_gaps():
        for url in [s["url"], *s.get("mirrors", [])]:
            if not allowed(url):
                results.append({"id": s["id"], "url": url, "status": "robots-disallowed"})
                continue
            try:
                body, ct = fetcher(url)
            except Exception as exc:
                results.append({"id": s["id"], "url": url, "status": f"error: {type(exc).__name__}"})
                continue
            ok, chars = is_usable(body, ct, min_chars, extractor)
            results.append({"id": s["id"], "url": url,
                            "status": "usable" if ok else "not-usable", "chars": chars})
            if ok:
                results[-1]["recovered"] = True
                break
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Probe open corpus gaps.")
    ap.add_argument("--min-chars", type=int, default=MIN_CHARS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = probe(min_chars=args.min_chars)
    recovered = [r for r in results if r.get("recovered")]
    if args.json:
        print(json.dumps({"recovered": recovered, "results": results}, indent=2))
    else:
        for r in results:
            print(f"  {r['id']:16} {r['status']:18} {r.get('chars', ''):>8}  {r['url']}")
        print(f"\nrecovered: {', '.join(r['id'] for r in recovered) if recovered else 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
