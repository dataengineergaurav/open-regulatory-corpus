#!/usr/bin/env python3
"""Bronze -> Silver: clean + dedup + chunk 512/50 -> Parquet"""
import hashlib, json, re
from pathlib import Path
import trafilatura
import fitz  # pymupdf
from datasets import Dataset

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

def chunk(text, tokenizer=None, size=512, overlap=50):
    # simple word-based chunk ~512 tokens ≈ 380 words
    words = text.split()
    if not words:
        return []
    step = size - overlap
    # approx tokens->words factor 1.33
    wsize = int(size * 0.75)
    woverlap = int(overlap * 0.75)
    wstep = wsize - woverlap
    chunks = []
    for i in range(0, len(words), wstep):
        c = " ".join(words[i:i+wsize])
        if len(c.split()) < 50:
            continue
        chunks.append(c)
        if i + wsize >= len(words):
            break
    return chunks

def main(run_id=None):
    bronze = Path("data/bronze/latest") if run_id is None else Path("data/bronze")/run_id
    if not bronze.exists():
        # resolve latest symlink or newest dir
        candidates = sorted(Path("data/bronze").glob("20*"), reverse=True)
        bronze = candidates[0] if candidates else bronze
    print(f"Building silver from {bronze}")
    raw_dir = bronze / "raw"
    rows = []
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
        chunks = chunk(text)
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

if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv)>1 else None)
