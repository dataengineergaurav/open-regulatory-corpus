#!/usr/bin/env python3
"""Read-only snapshot of the Open Regulatory Corpus state for the compliance-officer skill.

Prints the source inventory, per-source manifest outcome and chunk counts, plus the live gap
list (public frameworks with zero chunks). Reads artifacts only; never writes or fetches.

Usage:
  python .commandcode/skills/compliance-officer/scripts/state_snapshot.py
  python .commandcode/skills/compliance-officer/scripts/state_snapshot.py --json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

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
DOMAIN_OF = {fid: d for d, fids in DOMAINS.items() for fid in fids}


def load_sources() -> list[dict]:
    return json.loads((ROOT / "data/sources.json").read_text())


def load_manifest() -> tuple[list[dict], str]:
    bronze = ROOT / "data/bronze"
    run = bronze / "latest"
    label = "latest"
    if not run.exists():
        candidates = sorted(bronze.glob("20*"), reverse=True)
        if not candidates:
            return [], "none"
        run, label = candidates[0], candidates[0].name
    manifest = run / "manifest.jsonl"
    if not manifest.exists():
        return [], label
    rows = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
    return rows, label


def load_chunks() -> tuple[dict[str, int], dict]:
    parquet = ROOT / "data/silver/compliance_chunks.parquet"
    if not parquet.exists():
        return {}, {"error": "parquet not found"}
    try:
        import pandas as pd

        df = pd.read_parquet(parquet)
        stems = df.framework_id.astype(str).str.split("_pdf").str[0]
        counts = stems.value_counts().to_dict()
        return {str(k): int(v) for k, v in counts.items()}, {
            "chunks": int(len(df)),
            "docs": int(df.sha256.nunique()),
            "frameworks": int(stems.nunique()),
        }
    except Exception as exc:
        return {}, {"error": f"could not read parquet: {type(exc).__name__}: {exc}"}


def manifest_status(rows: list[dict], fid: str) -> str:
    related = [r for r in rows if r.get("id") == fid or str(r.get("id", "")).startswith(fid + "_pdf")]
    if not related:
        return "-"
    primary = next((r for r in related if r.get("id") == fid), related[0])
    status = primary.get("status", "?")
    ok_count = sum(1 for r in related if r.get("status") == "ok")
    if ok_count > 1 and status == "ok":
        return f"ok+{ok_count - 1}pdf"
    return status


def build() -> dict:
    sources = load_sources()
    rows, run_label = load_manifest()
    counts, silver = load_chunks()

    public = [s for s in sources if s.get("public")]
    skipped = [s for s in sources if not s.get("public")]
    present = set(counts)
    gaps = sorted(s["id"] for s in public if s["id"] not in present)

    table = []
    for s in sources:
        fid = s["id"]
        table.append({
            "id": fid,
            "domain": DOMAIN_OF.get(fid, "(unmapped)"),
            "public": bool(s.get("public")),
            "manifest": manifest_status(rows, fid),
            "chunks": counts.get(fid, 0),
        })

    ok = sum(1 for r in rows if r.get("status") == "ok")
    sk = sum(1 for r in rows if r.get("status") == "skipped_public_only")
    er = sum(1 for r in rows if r.get("status") == "error")

    return {
        "repo": str(ROOT),
        "run": run_label,
        "sources_total": len(sources),
        "sources_public": len(public),
        "sources_skipped": len(skipped),
        "manifest": {"ok": ok, "skipped": sk, "error": er, "lines": len(rows)},
        "silver": silver,
        "frameworks_present": len(present & {s["id"] for s in public}),
        "gaps": gaps,
        "table": table,
    }


def render(snap: dict) -> str:
    out = []
    out.append(f"# Corpus state — run `{snap['run']}`")
    out.append("")
    out.append(
        f"Sources: **{snap['sources_total']}** = {snap['sources_public']} public + "
        f"{snap['sources_skipped']} skipped (paywalled)"
    )
    s = snap["silver"]
    if "chunks" in s:
        out.append(
            f"Silver: **{s['chunks']:,}** chunks · {s['docs']} docs · "
            f"**{snap['frameworks_present']}/{snap['sources_public']}** public frameworks present"
        )
    else:
        out.append(f"Silver: unavailable ({s.get('error')})")
    m = snap["manifest"]
    out.append(
        f"Manifest: {m['ok']} ok · {m['skipped']} skipped · {m['error']} error ({m['lines']} lines)"
    )
    out.append("")
    gaps = snap["gaps"]
    out.append(f"## Gap list ({len(gaps)} public frameworks with 0 chunks)")
    out.append("")
    out.append(", ".join(f"`{g}`" for g in gaps) if gaps else "none — every public framework yields chunks")
    out.append("")
    out.append("## Per-source status")
    out.append("")
    out.append("| id | domain | public | manifest | chunks |")
    out.append("|---|---|---|---|---|")
    for r in snap["table"]:
        pub = "yes" if r["public"] else "NO (skipped)"
        out.append(f"| `{r['id']}` | {r['domain']} | {pub} | {r['manifest']} | {r['chunks']} |")
    out.append("")
    out.append("Legend: `ok` = fetched · `error` = WAF/timeout · `skipped_public_only` = paywalled. "
               "A source can be `ok` yet have 0 chunks (JS shell / WAF page / filtered at Silver) "
               "— that is still a gap.")
    return "\n".join(out)


def main() -> int:
    snap = build()
    if "--json" in sys.argv:
        print(json.dumps(snap, indent=2))
    else:
        print(render(snap))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
