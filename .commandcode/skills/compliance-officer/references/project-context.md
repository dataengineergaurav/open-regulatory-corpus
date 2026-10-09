# Project Context — Open Regulatory Corpus

Condensed, accurate understanding of what this repository is and how it works. Read this when a
proposal needs to reason about the pipeline, schema, provenance, or invariants. The authoritative
docs are in `docs/` — if this file and `docs/` disagree, trust `docs/` and say so.

---

## What it is

A public-only, machine-readable corpus of the rules governing **AI, privacy, cybersecurity,
finance, and health/access/trade** — scraped, cleaned, chunked, and shipped monthly. It exists so
that anyone building a governance/compliance/policy assistant does not have to re-scrape the same
documents. Public sources only: paywalled standards are recorded as skipped, never reproduced.

> **Not legal advice.** The corpus is a convenience copy of public sources; always verify against
> the authoritative URL in `data/sources.json`.

## Medallion model

```
 SOURCES            BRONZE                SILVER              (future) GOLD
 sources.json  →    raw bytes        →    chunks          →   vectors
 46 entries         58 files              1,519 rows          embeddings
 38 public          + manifest.jsonl      + parquet
 8 skipped          + headers/            + silver_stats.json
 ── curated ──►     ── immutable ──►      ── derived ──►      ── future ──
```

| Stage | Location | Mutability | Reproducible? |
|---|---|---|---|
| Sources | `data/sources.json` | Hand-edited (only curated input) | n/a |
| Bronze | `data/bronze/<run_id>/` | **Append-only, never edited** | **No** (the web changes) |
| Silver | `data/silver/` | Overwritten each build | **Yes**, from Bronze |
| Gold | *(planned)* | — | from Silver |

The asymmetry is deliberate: **Bronze is an archive, Silver is a cache.** Raw and headers are
gitignored (Release assets, ~43 MB/run); the parquet, manifest and stats stay in git.

## Components

- **`data/sources.json`** — flat JSON array; the single source of truth. The only hand-edited file.
  `{"id","url","public"}`. Nothing else hard-codes a URL. 46 entries = 38 public + 8 paywalled.
- **`scraper/compliance_scraper/spiders/generic.py`** — one data-driven spider. Discovers secondary
  PDFs (`_pdfN`), unwraps the CJIS `/view` viewer, obeys `robots.txt`, autothrottles, records
  failures via `errback` into the manifest.
- **`scraper/compliance_scraper/pipelines.py`** — `RawPipeline`: writes verbatim bytes to `raw/`,
  extension chosen by **magic bytes → content-type → URL**; writes `headers/<ID>.json`; appends
  `ok` rows; repoints the `latest` symlink on `close_spider`.
- **`scripts/build_silver.py`** — the only place extraction lives. trafilatura (+ tag-strip
  fallback) for HTML, PyMuPDF page-tagged for PDF; filters WAF/nav dumps and docs <200 chars;
  dedups by `sha256` of extracted text; chunks 512/50 (≈384 words, min 50). Emits parquet + stats.
- **`scripts/verify_bronze.py`** / **`scripts/verify_silver.py`** — executable assertions, wired
  into CI and the monthly release. A run that fails the invariants never publishes.
- **`scripts/publish_hf.py`** / **`scripts/sync_published.py`** — push Silver + card to Hugging
  Face, and rewrite the published numbers in `README.md` / `HF_DATASET_CARD.md` / GitHub About from
  the artifacts (idempotent; `--check` fails on drift).

## Silver schema (`data/silver/compliance_chunks.parquet`)

| Column | Type | Meaning |
|---|---|---|
| `framework_id` | string | Stem, or stem + `_pdfN` for a secondary document |
| `chunk_id` | string | `{framework_id}-{index}`, unique across the corpus |
| `text` | string | The chunk (the payload) |
| `source` | string | Bronze path, e.g. `data/bronze/latest/raw/SOX_pdf1.pdf` |
| `kind` | string | `pdf` or `html` |
| `token_est` | float | `len(text.split()) * 1.33` (an estimate by design) |
| `sha256` | string | Hash of the **extracted document text**; groups a doc's chunks |

Roll a framework up with `df.framework_id.str.split("_pdf").str[0]` (the `stem`).

## Provenance chain

```
parquet row
 └─ source:  data/bronze/latest/raw/<ID>.pdf
     └─ manifest.jsonl row → id, sha256_raw, bytes, fetched_at
         └─ url  ←  sources.json {"id": <ID>, ...}
```

Manifest line shapes (three, distinguished by `status`): `ok` (with `bytes`, `sha256_raw`,
`content_type`, `fetched_at`), `skipped_public_only` (paywalled; no request made), `error` (WAF
403 / timeout). Current run: **58 ok · 8 skipped · 4 error = 70 lines**.

## Commands (pixi tasks)

| Task | Does |
|---|---|
| `pixi run crawl run_id=<YYYY-MM-DD>` | Fetch all `public` sources into Bronze |
| `pixi run verify-bronze` / `verify-silver` | Assert the invariants |
| `pixi run build-silver` | Extract, dedup, chunk → parquet |
| `pixi run pipeline run_id=<…>` | crawl → verify-bronze → build-silver → verify-silver |
| `pixi run check-docs` | Exit 1 if published numbers drifted |
| `pixi run sync-published` | Rewrite README / HF card / GitHub About from artifacts |

## Verification invariants (respect these in every proposal)

- `verify_bronze`: `len(ok)` matches raw/header files on disk (±1 for the CJIS html+pdf stem
  collision); **exactly 8** `skipped_public_only`; **≥34** `ok`.
- `verify_silver`: parquet exists; **≥300** rows.
- `check-docs`: README and HF card numbers must equal the values derived from the artifacts.

**Implication:** adding a paywalled entry changes the skipped count and breaks `verify_bronze`; any
change that moves chunks/sources changes the published numbers and will drift `check-docs` until
`sync-published` runs. Always call this out in the proposal.

## Domains (the canonical map)

```python
DOMAINS = {
  "AI Governance":        ["NIST-AI-RMF","NIST-AI-600-1","EU-AI-ACT","OMB-M25-21","OMB-M25-22",
                           "OWASP-LLM-2026","CO-AI","TX-TRAIGA","SG-MODEL-AI"],
  "Privacy & Data":       ["GDPR","CCPA-CPRA","FERPA","COPPA","UK-DP-AI","BR-LGPD",
                           "AU-PRIVACY-AI","DOJ-DSP"],
  "Cybersecurity":        ["NIST-CSF2","NIST-800-53","NIST-800-171","FEDRAMP","CMMC",
                           "CJIS-6.1","IRS-1075"],
  "Financial":            ["SOX","GLBA","NYDFS-500","FRB-MRM-2026","ECOA-REG-B","NAIC-AI"],
  "Health/Access/Trade":  ["HIPAA","HHS-PART2","SECTION-508","ONC-HTI1","FDA-AI-MD",
                           "NYC-LL144","IL-AIVIA","EAR"],
}
```

## The gaps (current run)

Seven public frameworks yield **0 chunks** — a *recoverable* gap, not a missing source:

| Framework | Cause |
|---|---|
| `GDPR`, `EU-AI-ACT` | EUR-Lex serves a JavaScript shell (~2 KB) |
| `HIPAA`, `HHS-PART2`, `CMMC` | WAF HTTP 403 (Akamai) |
| `IL-AIVIA` | Request timed out |
| `BR-LGPD` | URL returns an HTML wrapper, not the PDF |

Distribution is skewed: `CJIS-6.1` (466), `IRS-1075` (228), `SOX` (226) ≈ 55% of all chunks.

## Roadmap (align proposals to this)

1. **Recover the gaps** — the headline goal; a shrinking missing set is the project's definition of progress.
2. **Gold stage** — optional embeddings/vector index; must consume Silver without mutating it.
3. **Exact token counts** — swap `token_est` for a real tokenizer where precision matters.
4. **Automated drift detection** — diff `sha256_raw` across releases to flag changed documents.

## Licensing & ethics

- Code MIT; data CC-BY-4.0 where applicable; underlying source documents retain their terms.
- Public-only is enforced **before a single request**: `"public": false` means never fetched.
- The project crawls politely on purpose (robots.txt, autothrottle, concurrency 2). Never propose
  working around that.
