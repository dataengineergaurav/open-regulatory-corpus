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
 sources.json  →    raw bytes        →    chunks          →   crosswalks
 46 entries         raw files            derived rows         (model-free)
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
gitignored (Release assets, roughly <!-- sync:raw_mib -->46 MB<!-- /sync:raw_mib --> per run); the parquet, manifest and stats stay in git.

## Components

- **`data/sources.json`** — flat JSON array; the single source of truth. The only hand-edited file.
  `{"id","url","public","mirrors"?}`. Nothing else hard-codes a URL. 46 entries = 38 public + 8 paywalled.
  Validated by `scripts/validate_sources.py` against `data/sources.schema.json` (CI on every PR).
- **`scraper/compliance_scraper/spiders/generic.py`** — one data-driven spider. Discovers secondary
  PDFs (`_pdfN`), unwraps the CJIS `/view` viewer, obeys `robots.txt`, autothrottles, and falls back
  through `mirrors` when a response is empty / a shell / a WAF page / an error. Failures go to the
  manifest via `errback`.
- **`scraper/compliance_scraper/pipelines.py`** — `RawPipeline`: writes verbatim bytes to `raw/`,
  extension chosen by **magic bytes → content-type → URL**; writes `headers/<ID>.json`; appends
  `ok` rows; repoints the `latest` symlink on `close_spider`.
- **`scripts/build_silver.py`** (+ `scripts/silver_utils.py`) — the only place extraction lives.
  trafilatura (+ tag-strip fallback) for HTML, PyMuPDF page-tagged for PDF; filters WAF/nav dumps
  and docs <200 chars; dedups by `sha256` of extracted text; chunks 512/50 (≈384 words, min 50),
  with opt-in `--section-aware`. Emits parquet + stats + `index/<run>.json` + `quality_report.json`.
- **`scripts/verify_bronze.py`** / **`verify_silver.py`** / **`verify_sources.py`** — executable
  assertions + acquisition health, wired into CI. A run that fails the invariants never publishes.
- **`scripts/detect_drift.py`** / **`build_changelog.py`** — diff two runs (extracted-text hash,
  raw fallback) and render the release changelog.
- **`scripts/build_balanced_slice.py`** — the capped companion slice; **`probe_gaps.py`** — the
  weekly gap watch's engine.
- **`scripts/publish_hf.py`** / **`sync_published.py`** — push Silver + card to Hugging Face, and
  rewrite the published numbers in `README.md` / `HF_DATASET_CARD.md` / GitHub About from the
  artifacts (idempotent; `--check` fails on drift).

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
`content_type`, `fetched_at`), `skipped_public_only` (paywalled; no request made), `error` (non-200
/ WAF). Current run: **57 ok · 8 skipped · 3 error = 68 lines**.

## Commands (pixi tasks)

| Task | Does |
|---|---|
| `RUN_ID=<YYYY-MM-DD> pixi run crawl` | Fetch all `public` sources into Bronze |
| `pixi run verify-bronze` / `verify-silver` / `verify-sources` | Assert the invariants / report gaps |
| `pixi run build-silver` | Extract, dedup, chunk → parquet (+ index, quality report) |
| `RUN_ID=<YYYY-MM-DD> pixi run pipeline` | crawl → verify-bronze → build-silver → verify-silver |
| `pixi run detect-drift` / `build-changelog` | Diff two runs / render the release changelog |
| `pixi run check-docs` | Exit 1 if published numbers drifted |
| `pixi run sync-published` | Rewrite README / HF card / GitHub About from artifacts |

## Verification invariants (respect these in every proposal)

- `verify_bronze`: `len(ok)` matches raw/header files on disk (±1 for the CJIS html+pdf stem
  collision); the skipped count **equals** the `public: false` entries in `sources.json`; `ok` is at
  least one per public source. All **derived from the registry**, no magic numbers.
- `verify_silver`: parquet exists; **≥300** rows.
- `verify_sources` / `check-docs`: gaps are reported as data; README and HF card numbers must equal
  the values derived from the artifacts.

**Implication:** adding a framework changes the *derived* expectations (skipped count, `ok` floor)
and the published numbers — `check-docs` drifts until `sync-published` runs. Always call this out.

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

## The gaps (current run, `<!-- sync:run_id -->2026-10-09<!-- /sync:run_id -->`)

A *recoverable* gap, not a missing source:

<!-- sync:gaps_table -->
**5** of the 38 public frameworks currently produce **zero chunks**:

| Framework | Why it's empty |
|---|---|
| `BR-LGPD`, `SG-MODEL-AI` | Served a shell / wrapper page (filtered at the Silver stage) |
| `ECOA-REG-B`, `NAIC-AI`, `NYDFS-500` | The server returned a non-200 response |
<!-- /sync:gaps_table -->

The earlier EUR-Lex pair (`GDPR`, `EU-AI-ACT`) and `HIPAA` / `HHS-PART2` / `CMMC` / `IL-AIVIA`
**were recovered via `mirrors`** — a good worked example for a recovery proposal.

Distribution is skewed: `CJIS-6.1`, `IRS-1075`, and `SOX` together are <!-- sync:top3_share -->~45%<!-- /sync:top3_share --> of all chunks.

## Roadmap (align proposals to this)

1. **Recover the open gaps** — the headline goal; a shrinking missing set is the project's definition of progress. The weekly gap watch tracks it.
2. **Gold stage** — model-free derived artifacts (topic/control crosswalks, framework index, exact token counts); embeddings stay a consumer recipe. Must consume Silver without mutating it.
3. **Exact token counts** — swap `token_est` for a real tokenizer where precision matters.
4. **Drift detection** — shipped: `detect-drift` compares extracted-text hashes across runs (raw fallback) and feeds the release changelog.

## Licensing & ethics

- Code MIT; data CC-BY-4.0 where applicable; underlying source documents retain their terms.
- Public-only is enforced **before a single request**: `"public": false` means never fetched.
- The project crawls politely on purpose (robots.txt, autothrottle, concurrency 2). Never propose
  working around that.
