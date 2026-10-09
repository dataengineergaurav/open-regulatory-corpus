#!/usr/bin/env python3
"""Sync every published surface of the corpus from one source of truth.

The volatile corpus numbers (chunk/doc counts, sizes, top documents) are derived
from the artifacts in data/ and written into the marker regions of README.md and
HF_DATASET_CARD.md, then pushed to the GitHub "About" section and the Hugging
Face dataset card. Idempotent: it only writes or commits when something changed.

Usage:
  pixi run sync-published            # update files + GitHub About + HF card
  pixi run sync-published --check    # verify only, exit 1 on drift (CI)
  pixi run sync-published --no-about # skip the GitHub About section
  pixi run sync-published --no-hf    # skip the Hugging Face card upload
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpus_stats as cs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GH_REPO = os.environ.get("GH_REPO", "dataengineergaurav/open-regulatory-corpus")
HF_REPO = os.environ.get("HF_REPO_ID", "GauravGurjar/open-regulatory-corpus")
HF_URL = f"https://huggingface.co/datasets/{HF_REPO}"

TOPICS = [
    "ai-governance", "compliance", "dataset", "gdpr", "nist", "rag", "bronze-silver",
    "ai-regulation", "corpus", "cybersecurity", "finance", "healthcare", "legal",
    "open-data", "parquet", "privacy", "regulatory", "text-retrieval",
]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text()


def compute_stats() -> dict:
    """Everything published is derived here — the single source of truth."""
    import pyarrow.parquet as pq

    manifest = [json.loads(line) for line in _read("data/bronze/latest/manifest.jsonl").splitlines() if line.strip()]
    ok = [r for r in manifest if r.get("status") == "ok"]
    pdfs = sum(1 for r in ok if "pdf" in (r.get("content_type") or "").lower())
    raw_bytes = sum(r.get("bytes", 0) for r in ok)

    sources = json.loads(_read("data/sources.json"))

    df = pq.read_table(str(ROOT / "data/silver/compliance_chunks.parquet")).to_pandas()
    stems = df.framework_id.str.split("_pdf").str[0]
    kinds = df.kind.value_counts().to_dict()
    top = stems.value_counts().head(4)

    public_ids = [s["id"] for s in sources if s["public"]]
    status_by_id: dict[str, str] = {}
    for r in manifest:
        status_by_id.setdefault(str(r.get("id", "")).split("_pdf")[0], str(r.get("status")))
    present = {str(x) for x in stems}
    gaps = [{"id": i, "status": status_by_id.get(i, "missing")}
            for i in sorted(public_ids) if i not in present]

    return {
        "sources_total": len(sources),
        "sources_public": sum(1 for s in sources if s["public"]),
        "sources_skipped": sum(1 for s in sources if not s["public"]),
        "manifest_total": len(manifest),
        "ok": len(ok),
        "skipped": sum(1 for r in manifest if r.get("status") == "skipped_public_only"),
        "error": sum(1 for r in manifest if r.get("status") == "error"),
        "raw_pdfs": pdfs,
        "raw_htmls": len(ok) - pdfs,
        "raw_mib": round(raw_bytes / 1024 / 1024),
        "chunks": len(df),
        "docs": int(df.sha256.nunique()),
        "frameworks_present": int(stems.nunique()),
        "tokens": int(df.token_est.sum()),
        "chunk_pdf": int(kinds.get("pdf", 0)),
        "chunk_html": int(kinds.get("html", 0)),
        "median_words": int(df.text.str.split().str.len().median()),
        "top": [(str(k), int(v)) for k, v in top.items()],
        "gaps": gaps,
        "run_id": os.path.basename(os.path.realpath(ROOT / "data/bronze/latest")),
    }


MARKER = re.compile(r"<!-- sync:([A-Za-z0-9_]+) -->(.*?)<!-- /sync:\1 -->", re.S)


def resolve(name: str) -> str:
    """Render a marker name: a renderer, else a scalar key; unknown names raise KeyError."""
    if name in cs.RENDERERS:
        return cs.RENDERERS[name]()
    vals = cs.values()
    if name in vals:
        return vals[name]
    raise KeyError(name)


def sync_markers(text: str) -> tuple[str, list[str]]:
    """Resolve every marker in `text`; return the new text and any unknown names."""
    unknown: list[str] = []

    def repl(m: re.Match) -> str:
        name = m.group(1)
        try:
            value = resolve(name)
        except KeyError:
            unknown.append(name)
            return m.group(0)
        return f"<!-- sync:{name} -->{value}<!-- /sync:{name} -->"

    return MARKER.sub(repl, text), unknown


def sync_markers_file(rel: str, check: bool) -> bool:
    """Resolve the markers in one file; return True if it drifted or had unknown names."""
    text = _read(rel)
    new, unknown = sync_markers(text)
    for name in unknown:
        print(f"  !! {rel}: unknown marker name {name!r}")
    drifted = new != text or bool(unknown)
    if drifted and not check:
        (ROOT / rel).write_text(new)
    return drifted


def desired_description(s: dict) -> str:
    return (
        f"Public-only corpus of AI, privacy, cybersecurity, finance & health regulations — "
        f"{s['sources_public']} frameworks → {s['chunks']:,} RAG-ready chunks. "
        f"Bronze → Silver medallion pipeline, monthly releases."
    )


def _gh(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def sync_about(s: dict, check: bool) -> bool:
    probe = _gh(["api", f"repos/{GH_REPO}", "--jq", "{description,homepage}"])
    if probe.returncode != 0:
        print(f"  !! gh not usable ({probe.stderr.strip()[:120]}) — skipping About")
        return False
    cur = json.loads(probe.stdout)
    names = json.loads(_gh(["api", f"repos/{GH_REPO}/topics", "--jq", ".names"]).stdout or "[]")
    drifted = (
        cur.get("description") != desired_description(s)
        or cur.get("homepage") != HF_URL
        or set(names) != set(TOPICS)
    )
    if not drifted or check:
        return drifted
    r = _gh(["api", "-X", "PATCH", f"repos/{GH_REPO}",
             "-f", f"description={desired_description(s)}", "-f", f"homepage={HF_URL}"])
    if r.returncode != 0:
        print(f"  !! About description/homepage not updated: {r.stderr.strip()[:160]}")
    topic_args = [a for t in TOPICS for a in ("-f", f"names[]={t}")]
    r = _gh(["api", "-X", "PUT", f"repos/{GH_REPO}/topics", *topic_args])
    if r.returncode != 0:
        print(f"  !! About topics not updated: {r.stderr.strip()[:160]}")
    return True


def sync_hf(check: bool) -> bool:
    from huggingface_hub import HfApi, hf_hub_download

    local = _read("HF_DATASET_CARD.md")
    try:
        remote = Path(hf_hub_download(HF_REPO, "README.md", repo_type="dataset")).read_text()
    except Exception as exc:  # network/repo absent — treat as needing push
        remote = None
        print(f"  (could not read remote card: {type(exc).__name__})")
    if remote == local:
        return False
    if not check:
        HfApi().upload_file(
            path_or_fileobj=str(ROOT / "HF_DATASET_CARD.md"),
            path_in_repo="README.md",
            repo_id=HF_REPO,
            repo_type="dataset",
            commit_message="docs: sync dataset card (automated)",
        )
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync published surfaces from corpus artifacts.")
    ap.add_argument("--check", action="store_true", help="verify only; exit 1 on drift")
    ap.add_argument("--no-about", action="store_true")
    ap.add_argument("--no-hf", action="store_true")
    args = ap.parse_args()

    stats = compute_stats()
    print(f"stats: {stats['chunks']:,} chunks · {stats['docs']} docs · "
          f"{stats['frameworks_present']}/{stats['sources_public']} frameworks · run {stats['run_id']}")

    docs = ("README.md", "HF_DATASET_CARD.md", "docs/FAQ.md")
    drift = False
    for rel in docs:
        d = sync_markers_file(rel, args.check)
        print(f"  {rel}: {'DRIFT' if d else 'ok'}")
        drift |= d

    if not args.no_about:
        d = sync_about(stats, args.check)
        print(f"  GitHub About: {'DRIFT' if d else 'ok'}")
        drift |= d
    if not args.no_hf:
        d = sync_hf(args.check)
        print(f"  Hugging Face card: {'DRIFT' if d else 'ok'}")
        drift |= d

    if args.check:
        if drift:
            print("\nDRIFT DETECTED — run `pixi run sync-published` to fix.")
            return 1
        print("\nAll published surfaces in sync.")
        return 0
    print("\nSynced." if drift else "\nAlready in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
