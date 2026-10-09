#!/usr/bin/env python3
"""Bronze -> Silver: clean + dedup + chunk 512/50 -> Parquet"""
import argparse
import hashlib, json, re
from pathlib import Path
import trafilatura
import fitz  # pymupdf
from datasets import Dataset

import silver_utils as su


def extract_text(raw_path: Path):
    if raw_path.suffix == ".pdf":
        doc = fitz.open(raw_path)
        parts = []
        for i, page in enumerate(doc):
            t = page.get_text("text") or ""
            if t.strip():
                parts.append(f"[Page {i+1}]\n{t}")
        return "\n\n".join(parts), "pdf"
    else:
        html = raw_path.read_bytes().decode(errors="ignore")
        text = trafilatura.extract(html, include_comments=False) or ""
        # fallback: strip tags
        if len(text) < 500:
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text)[:200000]
        return text, "html"


def chunk(text, size=512, overlap=50):
    # simple word-based chunk ~512 tokens ≈ 380 words (default; unchanged)
    return su.chunk_window(text, size, overlap)


def main(run_id=None, section_aware=False):
    bronze = Path("data/bronze/latest") if run_id is None else Path("data/bronze")/run_id
    if not bronze.exists():
        # resolve latest symlink or newest dir
        candidates = sorted(Path("data/bronze").glob("20*"), reverse=True)
        bronze = candidates[0] if candidates else bronze
    print(f"Building silver from {bronze}")
    raw_dir = bronze / "raw"
    rows = []
    quality = []
    seen_hash = set()
    seen_iid = {}  # stem -> count for collision (CJIS html+pdf same stem)
    for p in sorted(raw_dir.glob("*")):
        iid = p.stem
        # handle CJIS html+pdf same stem collision: make pdf distinct
        if iid in seen_iid:
            # second file with same stem (CJIS-6.1.html + .pdf)
            iid = f"{iid}_{p.suffix[1:]}"
            # ensure uniqueness if still collides
            c = 1
            base = iid
            while iid in seen_iid:
                c += 1
                iid = f"{base}{c}"
        seen_iid[iid] = p
        text, kind = extract_text(p)
        text = text.strip()
        # ponytail: filter WAF challenge + nav dumps that polluted 2026-09-01_1910
        if len(text) < 200:
            print(f"skip {iid}: len {len(text)}")
            continue
        if "AwsWaf" in text or "JavaScript is disabled" in text or "Enable JavaScript and then reload" in text:
            print(f"skip {iid}: WAF challenge")
            continue
        if "Creative Commons" in text and "BR-LGPD" in iid:
            print(f"skip {iid}: nav (BR-LGPD wrapper)")
            continue
        if "window.env" in text and "BR-LGPD" in iid:
            print(f"skip {iid}: nav (BR-LGPD wrapper)")
            continue
        # dedup across framework_id (CJIS duplicate pdf)
        h = hashlib.sha256(text.encode()).hexdigest()
        if h in seen_hash:
            print(f"skip {iid}: dup sha {h[:8]}")
            continue
        seen_hash.add(h)
        # section-aware chunking is opt-in; falls back when too few headings are found
        chunks = None
        if section_aware:
            chunks = su.chunk_sections(text)
        if chunks is None:
            chunks = su.chunk_window(text)
        quality.append({
            "framework_id": iid, "kind": kind, "sha256": h,
            "chars": len(text), "chunks": len(chunks),
            "flags": su.quality_flags(text, kind),
        })
        for idx, c in enumerate(chunks):
            rows.append({"framework_id": iid, "chunk_id": f"{iid}-{idx}", "text": c, "source": str(p), "kind": kind, "token_est": len(c.split())*1.33, "sha256": h})
    print(f"chunks: {len(rows)} from {len(seen_hash)} docs")
    out = Path("data/silver")
    out.mkdir(parents=True, exist_ok=True)
    # clean parquet (one row per doc)
    # chunks parquet
    ds = Dataset.from_list(rows) if rows else Dataset.from_dict({"framework_id":[],"chunk_id":[],"text":[]})
    ds.to_parquet(str(out / "compliance_chunks.parquet"))
    print(f"Wrote {out/'compliance_chunks.parquet'} ({len(rows)} rows)")
    # write manifest summary
    (out / "silver_stats.json").write_text(json.dumps({"run_id": str(bronze), "chunks": len(rows), "docs": len(seen_hash)}, indent=2))
    # extraction-quality side report (flags only annotate; nothing is dropped here)
    (out / "quality_report.json").write_text(json.dumps({
        "run_id": str(bronze),
        "section_aware": section_aware,
        "docs": len(quality),
        "flagged": sum(1 for d in quality if d["flags"]),
        "entries": quality,
    }, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Bronze -> Silver builder")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--section-aware", action="store_true",
                    help="chunk on numbered section headings where present (default: fixed window)")
    args = ap.parse_args()
    main(args.run_id, args.section_aware)
