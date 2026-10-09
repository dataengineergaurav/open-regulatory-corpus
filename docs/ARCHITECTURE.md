# Architecture

How the Open Regulatory Corpus is put together, why it is put together that way, and where you'd hook in to change it.

If [`DATA_PIPELINE.md`](DATA_PIPELINE.md) is the *runbook* (what to type, what breaks), this document is the *design* (what the pieces are and why they exist). Read this first if you're new; read the runbook when you're operating.

---

## Design in one sentence

**Fetch once, keep everything raw and immutable, then derive clean data from it as many times as you like** — because the raw web is the one thing you can never reproduce.

That single idea explains almost every decision in the codebase.

---

## The medallion model

The project follows the medallion (Bronze → Silver → Gold) pattern common in data engineering, applied to regulatory documents.

```
        ┌──────────────────────────────────────────────────────────────┐
        │                                                              │
        │   SOURCES          BRONZE              SILVER       (future)  │
        │   ───────          ──────              ──────       ────────  │
        │                                                              │
        │  sources.json  →   raw bytes     →   chunks      →  vectors  │
        │  46 entries        58 files          1,519 rows      Gold     │
        │  38 public         + manifest        + parquet                │
        │  8 skipped         + headers         + stats                  │
        │                                                              │
        │  ─── trusted ───►  ─── immutable ──►  ── derived ──►  future  │
        │                    never mutated     rebuildable              │
        └──────────────────────────────────────────────────────────────┘
```

| Stage | Lives in | Mutability | Reproducible? | Cost to recreate |
|---|---|---|---|---|
| **Sources** | `data/sources.json` | Edited by hand (the only curated input) | n/a | Free |
| **Bronze** | `data/bronze/<run_id>/` | **Append-only** — never edited | **No** — the web changes | Expensive (network) |
| **Silver** | `data/silver/` | Overwritten each build | **Yes** — deterministic from Bronze | Cheap (local CPU) |
| **Gold** | *(planned)* | — | Yes from Silver | Moderate (embeddings) |

The asymmetry is the point. Bronze is treated as an **archive**; Silver is treated as a **cache**. You can throw Silver away and rebuild it a hundred times from the same Bronze and get the same bytes. You cannot re-crawl last month's portal and get the same bytes — pages get WAF'd, redirects move, content is revised. So Bronze is where the durability budget is spent.

---

## Components

Five moving parts. Each has one job.

### 1. The source registry — `data/sources.json`

A flat JSON array. This is the **single source of truth** and the only thing a human edits to change the corpus.

```json
{"id": "NIST-CSF2", "url": "https://nvlpubs.nist.gov/.../NIST.CSWP.29.pdf", "public": true}
{"id": "ISO-42001", "url": "https://www.iso.org/standard/42001",                "public": false}
```

- `id` — the stable framework code, used everywhere downstream.
- `url` — where to fetch it.
- `public` — the ethical switch. `false` means *record it as skipped; never fetch it*.

Nothing else in the codebase contains a URL. The spider iterates this file; the pipeline initialises the Bronze manifest from the `public: false` entries before a single request is made.

### 2. The spider — `scraper/compliance_scraper/spiders/generic.py`

One spider (`compliance`), driven entirely by the registry. It has three responsibilities beyond "download the URL":

- **PDF discovery.** When an HTML page contains links to plausible PDFs, it follows up to 2–3 of them (same-host only) and ingests them as secondary documents (`<ID>_pdf1`, `<ID>_pdf2`…). This is how a landing page turns into the actual standard.
- **Wrapper unwrapping.** `CJIS-6.1` is served at a `.pdf/view` viewer URL that returns HTML. The spider detects this and re-requests the same path with `/view` stripped to get the true PDF.
- **Error capture.** Failed requests (`errback`) are written straight into `manifest.jsonl` as `error` rows, so a timeout is a *recorded fact*, not a silent hole.

The spider deliberately obeys `robots.txt` and uses autothrottle — see [politeness](#politeness-is-a-feature) below.

### 3. The Bronze pipeline — `scraper/compliance_scraper/pipelines.py`

A Scrapy item pipeline (`RawPipeline`) that turns a fetched response into durable artifacts:

- resolves the `run_id` (from the CLI arg, or a timestamp),
- writes verbatim bytes to `raw/`, with the extension derived from **magic bytes and content-type**, not from the URL,
- writes full response metadata to `headers/<ID>.json`,
- appends an `ok` line (with `sha256` and byte count) to `manifest.jsonl`,
- on spider close, writes `scrapy_stats.json` and repoints the `latest` symlink.

### 4. The Silver builder — `scripts/build_silver.py`

The transformation stage. Pure function of Bronze → Silver:

```
for each raw file:
    extract text      (PyMuPDF for .pdf, trafilatura + fallback for .html)
    filter noise      (WAF challenge pages, nav chrome, too-short docs)
    dedup             (by sha256 of extracted text, across all frameworks)
    chunk             (512 tokens, 50 overlap, ≈384 words, min 50 words)
    emit row          {framework_id, chunk_id, text, source, kind, token_est, sha256}
write Parquet + silver_stats.json
```

It is intentionally the *only* place extraction logic lives. Change chunking here and nothing else needs to know.

### 5. Verification — `scripts/verify_bronze.py`, `scripts/verify_silver.py`

Executable assertions, not vibes. `verify_bronze` checks that the manifest's `ok` count matches the files on disk (allowing the known CJIS html+pdf stem collision), that exactly 8 sources are skipped, and that at least 34 documents landed. `verify_silver` checks that the parquet exists and has a plausible row count. Both are wired into CI and the monthly release, so a broken run fails loudly instead of publishing quietly.

---

## Data flow: the life of one byte

Follow the `NIST-CSF2` PDF from URL to chunk:

```
1. sources.json           {"id":"NIST-CSF2","url":"…pdf","public":true}
        │
2. GenericSpider          GET the URL (robots.txt checked, throttled)
        │
3. RawPipeline            bytes land at  raw/NIST-CSF2.pdf        ← magic bytes say %PDF
        │                 headers land at headers/NIST-CSF2.json
        │                 manifest += {status:"ok", bytes:1518858, sha256_raw:"3c31f4…"}
        │
4. latest symlink         data/bronze/latest → 2026-09-01_1903
        │
5. build_silver.py        PyMuPDF → page-tagged text → dedup → 512/50 chunks
        │
6. parquet row            framework_id=NIST-CSF2, chunk_id=NIST-CSF2-14,
        │                 text="Executives receive significant input…",
        │                 source=data/bronze/latest/raw/NIST-CSF2.pdf,
        │                 kind=pdf, token_est=510.7, sha256="…"
        │
7. release + HF           parquet published; SHA256SUMS generated
```

At every step the byte is traceable. A downstream RAG answer that cites chunk `NIST-CSF2-14` can be walked all the way back to a URL and a content hash.

---

## The crawling strategy

Regulatory sites are hostile to crawlers in ways that are mostly accidental, but occasionally deliberate. The strategy is *polite, honest, and persistent about recording failure*.

- **`ROBOTSTXT_OBEY = True`** — the crawler reads and respects robots.txt for every host.
- **Autothrottle + concurrency 2 + 1 s delay** — the crawl is intentionally slow. This is a public-good project crawling government sites; hammering them would be both rude and short-sighted.
- **HTTP cache (7 days)** — development runs don't re-hit live servers.
- **`RETRY_TIMES = 2`** — enough to ride out a transient blip, not enough to be a nuisance.
- **Magic-byte typing** — the store never lies about what a file *is* (see [decisions](#design-decisions)).
- **Errors are first-class** — a 403 becomes a manifest row, not a stack trace that vanishes.

---

## Design decisions

Each of these was a fork in the road. Here's the road taken and the road not.

| Decision | Chosen | Rejected alternative | Why |
|---|---|---|---|
| Source of truth | One JSON file | URLs scattered in code/config | Add a framework = add one object; trivial to review and diff |
| Paywalled standards | Skip and record | Scrape anyway / omit silently | Legal and ethical clarity; the *absence* is documented data |
| Raw storage | Verbatim, magic-byte-named | Pre-converted text | Bronze must be re-derivable; conversion is Silver's job |
| Chunking | Word-window 512/50 (`×0.75`) | Tokenizer-exact (`tiktoken`) | Zero heavy deps; ~1.33 words/token is accurate enough for retrieval |
| Dedup | Content `sha256` | Filename / URL | Same text under two URLs (CJIS viewer + direct) collapses correctly |
| HTML extraction | trafilatura + tag-strip fallback | BeautifulSoup bespoke rules | Fewer moving parts; fallback catches page-specific weirdness |
| PDF extraction | PyMuPDF, page-tagged | pdfplumber / OCR | Fast, robust, preserves `[Page N]` provenance; no OCR needed yet |
| Silver format | Parquet via `datasets` | CSV / JSONL | Columnar, compressed, directly compatible with the HF `datasets` ecosystem |
| Verification | Assertions in scripts | Manual eyeballing | CI can fail a bad run automatically |
| Scheduling | GitHub Actions cron | Local cron / Airflow | Zero infrastructure, free, auditable, versioned with the code |

### Why 512 / 50?

512 tokens is the sweet spot for RAG on regulatory prose: long enough to hold a full control statement or clause, short enough that its embedding stays coherent. The 50-token overlap prevents a rule from being decapitated at a boundary. The builder approximates tokens as `words × 1.33` (a well-worn English heuristic) so the whole stage runs with no tokenizer dependency — which is what lets the notebooks run in Colab with no GPU and no `pixi`.

### Politeness is a feature

The crawl is slow by design. The goal is a corpus that can keep running monthly for years without any host deciding to block it permanently. Speed was traded away on purpose.

---

## Failure philosophy

1. **Nothing fails silently.** Every source ends in exactly one of `ok`, `skipped_public_only`, or `error` in the manifest.
2. **Bad data is filtered at Silver, not Bronze.** WAF challenge pages are allowed to land (Bronze is verbatim), then dropped during extraction, where the rules are visible and testable.
3. **Gaps are measured.** The set of expected-vs-present frameworks is computed in the EDA notebook, so recovery is trackable across releases.
4. **Verification gates publication.** The monthly workflow runs `verify_bronze` and `verify_silver` before packaging. A run that fails the invariants doesn't become a release.

---

## Extending the corpus

### Add a framework

1. Append one object to [`data/sources.json`](../data/sources.json): `{"id": "MY-RULE", "url": "…", "public": true}`.
2. Run `pixi run pipeline run_id=<date>`. Done — the spider is data-driven; no code touches needed.

If the site needs a special fetch, look at how `CJIS-6.1` (`/view` unwrapping) or the PDF-discovery block in `generic.py` handles its case, and add a narrow rule there.

### Add a new extraction behavior

All extraction lives in `build_silver.py`'s `extract_text`. Add a branch by file type or by content sniff, keep the `(text, kind)` return contract, and the rest of the pipeline is unchanged.

### Add a new stage (the planned "Gold")

Gold — embeddings — should be a **new script** (`scripts/build_gold.py`) that reads `compliance_chunks.parquet` and writes an index. It must not modify Silver. That keeps the medallion invariant: each stage consumes the previous, produces a new artifact, and never mutates what it reads. The [cookbook](COOKBOOK.md#5--export-a-rag-ready-slice) already shows the slice shape a Gold stage would consume.

### Add a source that is neither HTML nor PDF

Broaden `extract_text` to return a new `kind` value (e.g. `docx`), and add the magic bytes to the extension logic in `pipelines.py`. The `kind` column downstream is already a free-form string, so nothing else breaks.

---

## Related reading

- **Runbook & troubleshooting:** [`DATA_PIPELINE.md`](DATA_PIPELINE.md)
- **Every field, defined:** [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md)
- **Doing things with the data:** [`COOKBOOK.md`](COOKBOOK.md)
- **Why things are missing:** [`FAQ.md`](FAQ.md)
