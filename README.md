# Open Regulatory Corpus

**A public-only, machine-readable corpus of the rules that govern AI, privacy, cybersecurity, finance, and health care — scraped, cleaned, chunked, and shipped every month.**

<!-- sync:headline -->38 public frameworks → 57 raw documents (46 MB) → **2,041** citation-ready chunks across **54** documents<!-- /sync:headline -->

Drop them into a RAG pipeline, a spreadsheet, or a research notebook — no crawler required to consume it.

[Releases](https://github.com/dataengineergaurav/open-regulatory-corpus/releases) · [Hugging Face](https://huggingface.co/datasets/GauravGurjar/open-regulatory-corpus) · [Documentation](#documentation) · [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/dataengineergaurav/open-regulatory-corpus/blob/main/notebooks/01_search.ipynb)

---

## Why this exists

Compliance text is public, but it is not *usable*. It hides in PDFs behind viewer wrappers, in 200-page CFR dumps, behind WAF-protected portals, and in HTML where the real content is 4% of the page. Anyone building an AI governance assistant, a policy gap analysis, or a fine-tuning set spends weeks re-scraping the same 38 frameworks and re-solving the same extraction problems.

This project does that once, in the open, and keeps doing it. It is deliberately **public-only**: if a framework is paywalled (most ISO standards, SOC 2, PCI-DSS), it is recorded as skipped rather than pirated. Every chunk carries its `source` path and a `sha256`, so a downstream answer can always point back to the exact document it came from.

> **Not legal advice.** The corpus is a convenience copy of public sources. Always verify against the authoritative URL in [`data/sources.json`](data/sources.json).

---

## Get the data

Three ways in, from zero-effort to fully reproducible.

**1. Python, one line (Hugging Face):**
```python
from datasets import load_dataset
ds = load_dataset("GauravGurjar/open-regulatory-corpus")["train"]
fda = ds.filter(lambda x: x["framework_id"] == "FDA-AI-MD")
```

**2. Download a release (no account, no crawler):**
```bash
# Silver only — the cleaned chunks (~2.0 MiB)
curl -L -O https://github.com/dataengineergaurav/open-regulatory-corpus/releases/latest/download/open-regulatory-silver-*.parquet

# Or the full Bronze landing zone (raw PDFs + HTML + headers)
curl -L -O https://github.com/dataengineergaurav/open-regulatory-corpus/releases/latest/download/open-regulatory-bronze-*.tar.gz
```
Every release ships a `SHA256SUMS` file alongside the artifacts.

**3. Run the whole pipeline yourself (from source):**
```bash
pixi install
RUN_ID=2026-09-01 pixi run pipeline
# crawl → verify-bronze → build-silver → verify-silver
```
Artifacts land in `data/bronze/<run_id>/raw/` (<!-- sync:raw_files -->57<!-- /sync:raw_files --> files) and `data/silver/compliance_chunks.parquet`.

---

## What's inside

38 public frameworks across five domains, plus 8 paywalled standards recorded as `skipped_public_only`.

| Domain | Frameworks |
|---|---|
| **AI Governance** (9) | NIST-AI-RMF, NIST-AI-600-1, EU-AI-ACT, OMB-M25-21, OMB-M25-22, OWASP-LLM-2026, CO-AI, TX-TRAIGA, SG-MODEL-AI\* |
| **Privacy & Data** (8) | GDPR, CCPA-CPRA, FERPA, COPPA, UK-DP-AI, BR-LGPD\*, AU-PRIVACY-AI, DOJ-DSP |
| **Cybersecurity** (7) | NIST-CSF2, NIST-800-53, NIST-800-171, FEDRAMP, CMMC, CJIS-6.1, IRS-1075 |
| **Financial** (6) | SOX, GLBA, NYDFS-500\*, FRB-MRM-2026, ECOA-REG-B\*, NAIC-AI\* |
| **Health / Access / Trade** (8) | HIPAA, HHS-PART2, SECTION-508, ONC-HTI1, FDA-AI-MD, NYC-LL144, IL-AIVIA, EAR |

`*` = **tracked but 0 chunks in the current Silver.** These are not missing by accident — see [the honest gaps](#the-honest-gaps) below.

**Skipped, by design (paywalled, 8):** ISO 42001 / 42005 / 23894 / 38507 / 5338 / 24028, SOC 2, PCI-DSS.

---

## The honest gaps

Data work is mostly about what *didn't* land, and pretending otherwise makes a corpus untrustworthy.

<!-- sync:gaps_table -->
**5** of the 38 public frameworks currently produce **zero chunks**:

| Framework | Why it's empty |
|---|---|
| `BR-LGPD`, `SG-MODEL-AI` | Served a shell / wrapper page (filtered at the Silver stage) |
| `ECOA-REG-B`, `NAIC-AI`, `NYDFS-500` | The server returned a non-200 response |
<!-- /sync:gaps_table -->

`SG-MODEL-AI` and `BR-LGPD` land as raw bytes but extract to noise — a WAF challenge and navigation chrome respectively — and are dropped at the Silver stage. The full remediation playbook lives in [`docs/DATA_PIPELINE.md`](docs/DATA_PIPELINE.md#troubleshooting). **Gaps are tracked as data, not hidden** — the missing set is watched weekly and recovering one is a measurable win release-over-release.

---

## The pipeline at a glance

A classic **medallion** architecture: raw bytes first, trust and structure later, never the other way around.

```
  data/sources.json                       scraper/  (Scrapy)
  46 sources, 38 public                        │
        │                                      │  rate-limited, robots.txt-obeying,
        ▼                                      │  magic-byte extension detection
  ┌─────────────┐                          ┌────┴─────┐
  │   SOURCES   │────── crawl ────────────▶│  BRONZE  │  verbatim bytes + manifest
  └─────────────┘                          └────┬─────┘  raw bytes + manifest
        │                                       │
        │                                       │  trafilatura (HTML) + PyMuPDF (PDF)
        │                                       │  dedup by sha256 · chunk 512 / 50
        │                                       ▼
        │                                  ┌───────────┐
        │                                  │  SILVER   │  compliance_chunks.parquet
        │                                  └─────┬─────┘  citation-ready chunks
        │                                        │
        ▼                                        ▼
   monthly GitHub Release  ◀────────── publish ──────────▶  Hugging Face dataset
   (bronze tar + silver parquet + balanced slice + changelog + SHA256SUMS)
```

**Bronze — full raw landing (`data/bronze/<run_id>/`)**
Verbatim bytes, never mutated. Files are named by *magic bytes*, not by URL guessing (a `.pdf` URL that returns HTML is stored as `.html` — the extension never lies). A `manifest.jsonl` records what happened to every source; `headers/<ID>.json` preserves the HTTP response; `scrapy_stats.json` captures crawl telemetry. `latest` is a symlink to the newest run.

**Silver — cleaned + chunked (`data/silver/compliance_chunks.parquet`)**
HTML is extracted with `trafilatura` (with a tag-strip fallback for stubborn pages); PDFs with PyMuPDF, page-tagged so you never lose the page reference. Documents are deduplicated by content hash, split into 512-token windows with 50 tokens of overlap (≈384 words per chunk), then written to Parquet via `datasets`. A per-run document index (`index/<run_id>.json`) records each document's extracted-text hash for drift detection.

---

## Silver schema

Seven columns, every one of them provenance-bearing:

| Column | Type | Example | Meaning |
|---|---|---|---|
| `framework_id` | string | `CJIS-6.1_pdf` | Framework stem; a `_pdfN` suffix marks a secondary document for the same framework |
| `chunk_id` | string | `CJIS-6.1_pdf-42` | Stable per-chunk identifier (`{framework_id}-{index}`) |
| `text` | string | `"Related Controls: SR-8..."` | The chunk itself — the payload |
| `source` | string | `data/bronze/latest/raw/CJIS-6.1.pdf` | Path back to the Bronze file |
| `kind` | string | `pdf` \| `html` | Which extractor produced it |
| `token_est` | float | `510.7` | Approximate tokens (`words × 1.33`) |
| `sha256` | string | `dba84a6e…` | Content hash of the **source document** (ties all chunks of a doc together) |

Full field-by-field reference: [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md).

---

## By the numbers

<!-- sync:stats_bullets -->
Measured from `data/silver/compliance_chunks.parquet` (run `2026-10-09`):

- **2,041** chunks across **54** documents, spanning **33 of 38** public frameworks
- **~1,029,983** estimated tokens of compliance text
- **1,292** PDF chunks / **749** HTML chunks
- **384**-word median chunk length
- Largest documents: **CJIS-6.1** (464), **IRS-1075** (228), **SOX** (226), **GDPR** (163)
- Bronze: **57** raw files (**25** PDF · **32** HTML, **46 MB**); manifest **57** ok · **8** skipped · **3** error
<!-- /sync:stats_bullets -->

> The top three documents are <!-- sync:top3_share -->~45%<!-- /sync:top3_share --> of all chunks. That's a real characteristic of regulatory text (CJIS and IRS-1075 are enormous), and something to weight for when sampling. A capped companion slice ships for exactly this reason.

---

## Documentation

| Doc | What you'll find |
|---|---|
| [`docs/README.md`](docs/README.md) | The map — start here if you're unsure |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How the pieces fit, why, and where to extend |
| [`docs/DATA_PIPELINE.md`](docs/DATA_PIPELINE.md) | Stage-by-stage runbook + troubleshooting |
| [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) | Every artifact and field, defined |
| [`docs/COOKBOOK.md`](docs/COOKBOOK.md) | Recipes: filter, search, compare, export for RAG |
| [`docs/FAQ.md`](docs/FAQ.md) | Gaps, licensing, provenance, roadmap |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Prioritized engineering roadmap — issues grouped Now / Next / Later |
| [`notebooks/`](notebooks/) | Runnable Colab notebooks (search, EDA, analysis) |
| [`.commandcode/skills/compliance-officer/`](.commandcode/skills/compliance-officer/SKILL.md) | Agent skill: audit the corpus, research current affairs, propose source updates |

The **`compliance-officer`** skill acts as the corpus's compliance officer — it audits how complete and current the corpus is, researches live regulatory affairs, and returns a **review-only proposal**. It never edits `sources.json` or runs the pipeline itself:

```
/compliance-officer gap-recovery      # find fetchable fixes for the empty frameworks
/compliance-officer currency-check    # is every tracked framework still current?
/compliance-officer drift-check       # did a document change without a version bump?
```

---

## Repository map

```
open-regulatory-corpus/
├── scraper/                  Scrapy project — the crawler
│   └── compliance_scraper/
│       ├── spiders/generic.py    one spider, driven entirely by data/sources.json
│       ├── pipelines.py          writes bytes, headers, manifest, latest symlink
│       └── settings.py           polite defaults: robots.txt, autothrottle, HTTP cache
├── scripts/
│   ├── build_silver.py       Bronze → cleaned, deduped, chunked Parquet
│   ├── silver_utils.py       chunking + extraction-quality helpers
│   ├── build_balanced_slice.py  capped per-framework slice (counter the top-3 skew)
│   ├── verify_bronze.py      asserts manifest/raw/header invariants
│   ├── validate_sources.py   validates data/sources.json against its schema
│   ├── verify_silver.py      asserts Silver row count + schema
│   ├── verify_sources.py     reports per-source acquisition health (gaps)
│   ├── probe_gaps.py         re-probes empty frameworks for usable text (gap watch)
│   ├── detect_drift.py       diffs two runs by extracted-text hash (drift report)
│   ├── build_changelog.py    renders a changelog (md + json) from the drift
│   ├── publish_hf.py         uploads Silver + card to Hugging Face
│   └── sync_published.py     keeps README / HF card / GitHub About in sync
├── data/
│   ├── sources.json          the single source of truth: 46 sources, 38 public
│   ├── sources.schema.json   JSON Schema for the registry (validated in CI)
│   ├── bronze/               raw landing zone (raw/ + headers/ are Release assets)
│   └── silver/               compliance_chunks.parquet + balanced slice + index/ + quality report
├── notebooks/                01_search · 02_silver_eda · 03_silver_analysis
├── docs/                     you are (one level) here
├── .commandcode/skills/      agent skills — compliance-officer (audit · research · proposals)
├── .github/workflows/        ci.yml + monthly-release.yml + gap-watch.yml
└── pixi.toml                 environment + named tasks (crawl, build-silver, pipeline…)
```

---

## How it stays fresh

A scheduled GitHub Action runs on the **1st of every month**: it crawls, verifies Bronze, builds and verifies Silver, packages the artifacts, cuts a GitHub Release with a `SHA256SUMS`, and publishes to Hugging Face. Every run is identified by a `run_id` (e.g. `<!-- sync:run_id -->2026-10-09<!-- /sync:run_id -->`), and Bronze keeps every run side-by-side, so history is never overwritten.

Each release also ships a **changelog** (`changelog-<run_id>.md`) listing the documents added, changed, or removed since the previous run — detected by diffing **extracted-text** hashes, so a framework that was revised in place shows up even without a version bump, while re-rendered page chrome does not. See [Releases](https://github.com/dataengineergaurav/open-regulatory-corpus/releases).

A weekly **gap watch** re-probes the empty frameworks and opens an issue if one starts serving text, so recovery is noticed rather than missed.

Want to add a framework? Add one object to [`data/sources.json`](data/sources.json) and open a PR — the spider is fully data-driven. See [`docs/ARCHITECTURE.md#extending-the-corpus`](docs/ARCHITECTURE.md#extending-the-corpus).

---

## License & disclaimer

- **Code:** [MIT](LICENSE)
- **Data:** CC-BY-4.0 where applicable — source documents retain their original terms.
- **Not legal advice.** This is a research and engineering artifact, not a compliance guarantee. Verify against the authoritative source for every framework.

Every source URL, with its public/paywalled status, is enumerated in [`data/sources.json`](data/sources.json).
