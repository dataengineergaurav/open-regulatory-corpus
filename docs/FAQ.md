# FAQ

The questions people actually ask, answered plainly — including the uncomfortable ones about what's missing.

**Contents**
- [What this is](#what-this-is)
- [The gaps](#the-gaps)
- [Trust & accuracy](#trust--accuracy)
- [Legal & licensing](#legal--licensing)
- [Using the data](#using-the-data)
- [Contributing & roadmap](#contributing--roadmap)

---

## What this is

### What is this project, in one paragraph?

A pipeline that fetches 38 public regulatory and compliance frameworks, stores the raw documents untouched, and derives a clean, chunked, provenance-tagged Parquet file (~1,519 rows) that's ready to drop into a RAG system, a research notebook, or a dataset. It re-runs monthly and publishes to GitHub Releases and Hugging Face.

### Who is it for?

- **AI/ML engineers** building governance, compliance, or policy assistants who don't want to re-scrape the same documents.
- **Researchers & NGOs** (the project explicitly aims to be useful to non-profits) who need a citable, versioned text corpus without a budget.
- **Anyone** who needs to compare what different regulations actually say about a topic, with sources attached.

### Which frameworks are included?

38 public frameworks across five domains — AI governance, privacy & data, cybersecurity, financial, and health/access/trade. The full list is in the [project README](../README.md#whats-inside). Eight paywalled standards (most ISO, SOC 2, PCI-DSS) are tracked but deliberately not fetched.

### How often is it updated?

Monthly. A scheduled GitHub Action runs on the 1st of each month, and each run gets a `run_id` (e.g. `2026-09-01_1903`). Bronze keeps every run side-by-side, so nothing is overwritten and you can always see what changed.

---

## The gaps

### Why are some frameworks empty?

Seven of the 38 public frameworks currently produce **zero chunks**. None of them are empty by accident:

| Framework | Cause |
|---|---|
| `GDPR`, `EU-AI-ACT` | EUR-Lex returns a JavaScript shell (~2 KB) instead of the regulation text |
| `HIPAA`, `HHS-PART2`, `CMMC` | The server returned HTTP 403 (Akamai WAF) |
| `IL-AIVIA` | The request timed out |
| `BR-LGPD` | The "PDF" URL actually serves an HTML wrapper page |

Two of these even land raw bytes in Bronze and then extract to noise (a WAF challenge, or navigation chrome), which the Silver stage filters out. The remediation notes are in [`DATA_PIPELINE.md`](DATA_PIPELINE.md#troubleshooting).

### Does the corpus hide these gaps?

No — the opposite. Every source ends in exactly one of `ok`, `skipped_public_only`, or `error` in the manifest, and the EDA notebook computes expected-vs-present frameworks so the missing set is visible and trackable. **Gaps are treated as data.** The measure of progress on this project is that the missing set gets smaller.

### Why not just scrape the paywalled standards anyway?

Because it would be wrong. ISO standards, SOC 2, and PCI-DSS are gated for a reason. The project is public-only by design: if a framework can't be legally and openly obtained, it's recorded as skipped rather than reproduced. That constraint is a feature, and it's enforced before a single HTTP request is made.

### The PAYWALLED ones show up in the docs — won't people search for them and find nothing?

They appear in domain lists (that's an accurate statement of the regulatory landscape) but they have `public: false` in `sources.json` and are marked "skipped, by design" everywhere. If you filter the actual data for them, you get zero rows — which is the honest answer.

---

## Trust & accuracy

### Is this legal advice?

**No.** It is a research and engineering artifact — a convenience copy of public sources, chunked for machines. Always verify against the authoritative URL for any framework before relying on it. Every source URL is in [`data/sources.json`](../data/sources.json).

### Can I trust the extracted text?

The extraction is good but not infallible, and PDFs are the riskier case (multi-column layouts, tables, and page furniture all exist in this corpus). That's exactly why **every chunk carries its `source` path and the source document's `sha256`** — you can always go back to the raw bytes and check. If a passage matters, verify it. The [provenance recipe](COOKBOOK.md#6--provenance-walk-a-chunk-back-to-its-source) walks a chunk to its URL.

### How do I cite a chunk?

Every row is self-identifying. Cite `framework_id`, `chunk_id`, and `source` (plus `sha256` for exactness). Example: *"CJIS Security Policy v6.1, chunk `CJIS-6.1_pdf-188`, from `data/bronze/latest/raw/CJIS-6.1.pdf`."*

### Why is some text noisy (tables, nav, page markers)?

Three honest reasons: PDFs contain tables and page headers that text extraction flattens into the stream; some HTML pages carry navigation chrome that survives extraction; and PDF pages are deliberately tagged with `[Page N]` so provenance isn't lost. The builders filter the worst offenders (WAF pages, nav dumps, sub-200-char documents) but don't aim for human-perfect prose — they aim for retrievable, citable chunks.

---

## Legal & licensing

### What license applies?

- **Code:** MIT — see [`LICENSE`](../LICENSE).
- **Data:** CC-BY-4.0 where applicable.
- **Underlying source documents:** retain their original terms. The corpus does not relicense government or third-party text.

### Can I use this commercially?

The *code* (MIT) and *tooling* are free to use however you like. For the *data*, the CC-BY-4.0 attribution terms apply, and the original sources' terms still govern their own text. Check the source's terms if you're doing anything high-stakes.

### Do you store copyrighted material?

The corpus stores publicly-available documents (this is a public-only project) plus minimal records of what was deliberately skipped. It does not reproduce paywalled standards.

---

## Using the data

### Do I need to run the crawler to use the data?

No. Download a release (Silver parquet or full Bronze tarball) or use the Hugging Face dataset in one line. Crawling is only for reproducing or extending the pipeline — see the [README](../README.md#get-the-data).

### Why are the chunks word-based rather than tokenizer-exact?

Because it removes a heavy dependency and lets the whole thing run in Colab with no GPU. `token_est = words × 1.33` is an accurate-enough English heuristic for retrieval. If you need exact counts, tokenize `text` yourself in a Gold stage — see [DATA_DICTIONARY.md](DATA_DICTIONARY.md#datasilvercompliance_chunksparquet).

### Why 512 tokens with 50 overlap?

512 is large enough to hold a whole control statement or clause (so its embedding stays coherent) and small enough to stay retrieval-friendly. The 50-token overlap prevents rules from being cut in half at window boundaries. Details in [ARCHITECTURE.md](ARCHITECTURE.md#why-512--50).

### Why doesn't the distribution look even across frameworks?

Because the source documents aren't even. `CJIS-6.1`, `IRS-1075`, and `SOX` are enormous and together are ~55% of all chunks. If you sample or train naively, those three will dominate — the [cookbook](COOKBOOK.md#8--sample-fairly-why-you-should-care-about-the-top-3) has a balancing recipe.

### Are there embeddings / a vector index?

Not yet. That's the planned **Gold** stage. Silver is deliberately the stopping point that needs no GPU, and Gold is designed to consume Silver without modifying it — see [ARCHITECTURE.md](ARCHITECTURE.md#add-a-new-stage-the-planned-gold).

---

## Contributing & roadmap

### How do I add a framework?

Add one object to [`data/sources.json`](../data/sources.json) and run the pipeline. The spider is data-driven, so no code change is usually needed. Sites with special behavior (viewer wrappers, multi-PDF landing pages) may need a narrow rule — see [ARCHITECTURE.md](ARCHITECTURE.md#extending-the-corpus).

### I found a wrong number or a broken doc link. What do I do?

Treat it as a bug. Docs are part of the product here; if a figure in the docs doesn't match the artifacts, that's a defect worth reporting. Numbers in the README and data dictionary are verified against the current parquet and manifest.

### What's on the roadmap?

Roughly, in order of value:

1. **Recover the gaps** — replace or mirror the WAF-blocked, JS-shell, and wrapper sources so `GDPR`, `EU-AI-ACT`, `HIPAA`, `HHS-PART2`, `CMMC`, `IL-AIVIA`, and `BR-LGPD` yield real chunks.
2. **Gold stage** — optional embeddings + a vector index built from Silver, kept as a separate, non-mutating stage.
3. **Exact token counts** — swap `token_est` for a real tokenizer where precision matters.
4. **Automated drift detection** — diff `sha256_raw` across releases to flag documents that changed.

### How do I report a problem or contribute?

Open an issue or PR on [GitHub](https://github.com/dataengineergaurav/open-regulatory-corpus). For a new source, the diff is usually a single line in `sources.json`.
