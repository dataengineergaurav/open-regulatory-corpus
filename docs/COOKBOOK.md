# Cookbook

Task-oriented recipes for the Silver corpus. Each one is runnable copy-paste, needs no GPU, and works in Colab. The runnable versions with outputs live in [`notebooks/`](../notebooks/).

**Ground rules for everything below:**

- Load once, then filter — don't re-read the parquet per cell.
- `framework_id` includes `_pdfN` suffixes; `stem` (split on `_pdf`) is the framework.
- Every answer you surface should be traceable to `source` + `sha256`. That's the whole point.

---

## 0 — Load the data

Pick whichever source you have. All three produce the same dataframe.

```python
import pandas as pd
from pathlib import Path

parquet = Path("data/silver/compliance_chunks.parquet")
if parquet.exists():
    df = pd.read_parquet(parquet)                                    # local
else:
    from datasets import load_dataset
    df = load_dataset("GauravGurjar/open-regulatory-corpus")["train"].to_pandas()  # HF

df["stem"] = df.framework_id.str.split("_pdf").str[0]
print(f"{len(df)} chunks · {df.framework_id.nunique()} framework_ids · "
      f"{df.stem.nunique()} frameworks · {df.sha256.nunique()} docs")
# 2041 chunks · 54 framework_ids · 33 frameworks · 54 docs
```

---

## 1 — Filter by framework or domain

The fastest path to a corpus slice.

```python
# One framework, primary document only
fda = df[df.framework_id == "FDA-AI-MD"]                    # 85 chunks

# All documents for a framework (primary + secondary PDFs), via stem
sox = df[df.stem == "SOX"]                                  # 226 chunks
print(sox.framework_id.unique())                            # ['SOX' 'SOX_pdf1' 'SOX_pdf2']

# Domain slice — reuse this map anywhere
DOMAINS = {
    "AI Governance":        ["NIST-AI-RMF","NIST-AI-600-1","EU-AI-ACT","OMB-M25-21",
                             "OMB-M25-22","OWASP-LLM-2026","CO-AI","TX-TRAIGA","SG-MODEL-AI"],
    "Privacy & Data":       ["GDPR","CCPA-CPRA","FERPA","COPPA","UK-DP-AI","BR-LGPD",
                             "AU-PRIVACY-AI","DOJ-DSP"],
    "Cybersecurity":        ["NIST-CSF2","NIST-800-53","NIST-800-171","FEDRAMP","CMMC",
                             "CJIS-6.1","IRS-1075"],
    "Financial":            ["SOX","GLBA","NYDFS-500","FRB-MRM-2026","ECOA-REG-B","NAIC-AI"],
    "Health/Access/Trade":  ["HIPAA","HHS-PART2","SECTION-508","ONC-HTI1","FDA-AI-MD",
                             "NYC-LL144","IL-AIVIA","EAR"],
}
def domain_slice(name):
    return df[df.stem.isin(DOMAINS[name])]

print(domain_slice("Privacy & Data").shape)   # (382, 8)
```

> Remember: `NYDFS-500`, `ECOA-REG-B`, `NAIC-AI`, `SG-MODEL-AI`, `BR-LGPD` are in these lists but currently yield **0 chunks**. Filtering is honest — you get what actually landed, nothing fabricated. See [`FAQ.md`](FAQ.md#why-are-some-frameworks-empty).

---

## 2 — Keyword search without embeddings

TF-IDF gets you surprisingly far on regulatory prose and needs no model download. Falls back to substring search if `scikit-learn` isn't installed.

```python
def search(df, query, k=5):
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vec = TfidfVectorizer(stop_words="english", max_features=5000)
        X = vec.fit_transform(df.text.tolist())
        scores = cosine_similarity(vec.transform([query]), X).flatten()
        top = scores.argsort()[::-1][:k]
        return [(scores[i], df.iloc[i]) for i in top]
    except ImportError:
        hits = df[df.text.str.contains(query, case=False, na=False)].head(k)
        return [(1.0, r) for _, r in hits.iterrows()]

for score, r in search(df, "incident response logging"):
    print(f"{score:.3f}  {r.framework_id:16} {r.chunk_id}")
    print(f"  {r.text[:200]}…")
    print(f"  ← {r.source}  sha:{r.sha256[:8]}\n")
```

**Why it works:** compliance language is terminologically rigid. "Breach notification", "risk assessment", "access control" appear nearly verbatim across frameworks, so lexical overlap is a strong signal — good enough for a first pass, and a fair baseline to beat with embeddings later.

---

## 3 — Compare frameworks on one theme

Ask the same question of every framework and rank the answers. This is the recipe for "does framework A address topic X, and how prominently?"

```python
def compare(df, query, frameworks):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    vec = TfidfVectorizer(stop_words="english", max_features=5000)
    X = vec.fit_transform(df.text.tolist())
    df = df.assign(score=cosine_similarity(vec.transform([query]), X).flatten())
    for fid in frameworks:
        sub = df[df.stem == fid].nlargest(2, "score")
        print(f"\n=== {fid}  ({len(df[df.stem==fid])} chunks) ===")
        for _, r in sub.iterrows():
            print(f"  {r.score:.3f}  {r.chunk_id}: {r.text[:180].replace(chr(10),' ')}…")

compare(df, "risk management", ["NIST-CSF2", "SOX", "IRS-1075", "FDA-AI-MD"])
```

---

## 4 — Domain rollup and vocabulary overlap

How much do two frameworks actually share? A Jaccard coefficient over top terms is a cheap, dependency-free signal.

```python
import re
from collections import Counter

STOP = {"the","and","for","are","with","this","that","from","have","will","shall","must"}
def top_terms(texts, k=30):
    c = Counter(w for t in texts for w in re.findall(r"[a-z]{3,}", t.lower()) if w not in STOP)
    return {w for w, _ in c.most_common(k)}

a = top_terms(df[df.stem == "NIST-CSF2"].text)
b = top_terms(df[df.stem == "SOX"].text)
print(f"Jaccard = {len(a & b) / len(a | b):.2f}")        # 0.09 — very different vocabularies
print("shared :", sorted(a & b))
print("only SOX:", sorted(b - a)[:10])
```

## Domain sizes (current run)

```
Cybersecurity          804 chunks   ← CJIS-6.1 dominates
Privacy & Data         382
Health/Access/Trade    368
Financial              255
AI Governance          232
```

---

## 5 — Export a RAG-ready slice

Produce a file an embedding job can consume directly (embeddings are a consumer concern, not a pipeline stage — see [Notes on embeddings](#notes-on-embeddings)).

```python
from pathlib import Path

keep = {"SOX","GLBA","NYDFS-500","FRB-MRM-2026","ECOA-REG-B","NAIC-AI",
        "NIST-CSF2","NIST-800-53","NIST-800-171","FEDRAMP","CJIS-6.1","IRS-1075"}
cols = ["framework_id","chunk_id","text","source","sha256","token_est"]

slice_df = df[df.stem.isin(keep)][cols].dropna()
print(f"{len(slice_df)} chunks, {slice_df.token_est.sum():,.0f} est. tokens")

out = Path("data/silver/fin_cyber_slice.parquet")
slice_df.to_parquet(out, index=False)

# jsonl — the common shape for embedding jobs (one chunk per line)
slice_df.to_json("fin_cyber_slice.jsonl", orient="records", lines=True)
```

**Include `framework_id`, `chunk_id`, `source`, and `sha256` in your vector store metadata.** They cost nothing and they're the difference between a RAG app that can cite its sources and one that can't.

---

## 6 — Provenance: walk a chunk back to its source

Given any chunk, recover the authoritative URL. This is the recipe that makes the corpus defensible.

```python
import json
from pathlib import Path

manifest = {}
for line in Path("data/bronze/latest/manifest.jsonl").read_text().splitlines():
    row = json.loads(line)
    manifest[row["id"]] = row

def provenance(chunk_row):
    fid = chunk_row.framework_id                       # e.g. "SOX_pdf1"
    m = manifest.get(fid, {})
    return {"framework_id": fid, "chunk_id": chunk_row.chunk_id,
            "source_url": m.get("url"), "status": m.get("status"),
            "raw_sha256": m.get("sha256_raw", "")[:12]}

print(provenance(df[df.chunk_id == "SOX_pdf1-113"].iloc[0]))
```

---

## 7 — Measure the gaps (track recovery)

The gaps are data. Compute them so you can see a framework return release over release.

```python
expected = {f for members in DOMAINS.values() for f in members}          # 38
present  = set(df.stem.unique())                                         # 33
missing  = sorted(expected - present)
print(f"expected {len(expected)}, present {len(present)}, missing {len(missing)}")
print(missing)
# ['BR-LGPD','ECOA-REG-B','NAIC-AI','NYDFS-500','SG-MODEL-AI']
```

Run this against each new month's parquet and log `missing`. A shrinking set is the definition of progress on this project. `pixi run verify-sources` and the weekly gap watch do this for you.

---

## 8 — Sample fairly (why you should care about the top 3)

The distribution is extremely skewed: `CJIS-6.1`, `IRS-1075`, and `SOX` together are **~45% of all chunks**. If you train or evaluate on the raw corpus, those three frameworks will dominate.

```python
# Naive: skewed
raw = df.sample(300, random_state=0)

# Better: cap per-framework contribution
cap = 30
balanced = (df.groupby("stem", group_keys=False)
              .apply(lambda g: g.sample(min(len(g), cap), random_state=0)))
print(f"{len(balanced)} chunks, max {balanced.stem.value_counts().max()} per framework")
```

**A balanced slice ships with the data.** `data/silver/balanced_slice.parquet` is this recipe already applied (cap 30, seed 0): 595 chunks, ≤30 per framework, so the big three fall from ~45% of the corpus to ~15% of the slice. Build it yourself with `python scripts/build_balanced_slice.py --cap 30`.

For retrieval evaluation, always report per-framework metrics, not a single blended number — a corpus-wide average is really an average over CJIS.

---

## 9 — Near-duplicate check across frameworks

Frameworks inherit text from each other (800-53 → 800-171 → IRS-1075 → CJIS). Detecting shared passages is a feature, not a bug.

```python
# Exact-text duplicates are already removed at build time (sha256 of doc).
# For *passage*-level overlap, hash a normalized prefix of each chunk:
import hashlib
def norm_prefix(t, n=100):
    return hashlib.sha1(" ".join(t.lower().split()[:n]).encode()).hexdigest()

dup = df[df.text.map(norm_prefix).duplicated(keep=False)]
print(f"{len(dup)} chunks share a 100-word opening with another chunk")
print(dup.groupby("stem").size().sort_values(ascending=False).head())
```

---

## Notes on embeddings

Embeddings are a **consumer** concern, not a pipeline stage. The slice from recipe 5 is exactly what an embedding job should consume:

```
Silver parquet  →  embed(text)  →  (vector, chunk_id, framework_id, source, sha256)
                                  →  FAISS / pgvector / whatever
```

Non-negotiables carried forward from Silver into any vector store: `chunk_id`, `framework_id`, `source`, `sha256`. Keeping embeddings outside the pipeline means Gold stays model-free and reproducible, and Silver keeps its rebuildable, no-GPU promise — see [ARCHITECTURE.md](ARCHITECTURE.md#add-a-new-stage-the-planned-gold).
