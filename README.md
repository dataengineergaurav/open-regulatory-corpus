# Open Regulatory Corpus

**A public-only, machine-readable corpus of the rules that govern AI, privacy, cybersecurity, finance, and health care — scraped, cleaned, chunked, and shipped every month.**

<!-- sync:headline -->
38 public frameworks → 58 raw documents (43 MB) → **1,519** citation-ready chunks across **54** documents
<!-- /sync:headline -->

Drop them into a RAG pipeline, a spreadsheet, or a research notebook — no crawler required to consume it.

[Releases](https://github.com/dataengineergaurav/open-regulatory-corpus/releases) · [Hugging Face](https://huggingface.co/datasets/GauravGurjar/open-regulatory-corpus) · [Documentation](#documentation) · [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/dataengineergaurav/open-regulatory-corpus/blob/main/notebooks/01_search.ipynb)

---

## Why this exists

Compliance text is public, but it is not *usable*. It hides in PDFs behind viewer wrappers, in 200-page CFR dumps, behind WAF-protected portals, and in HTML where the real content is 4% of the page. Anyone building an AI governance assistant, a policy gap analysis, or a fine-tuning set spends weeks re-scraping the same 38 documents and re-solving the same extraction problems.

This project does that once, in the open, and keeps doing it. It is deliberately **public-only**: if a framework is paywalled (most ISO standards, SOC 2, PCI-DSS), it is recorded as skipped rather than pirated. Every chunk carries its `source` path and a `sha256`, so a downstream answer can always point back to the exact document it came from.

> **Not legal advice.** The corpus is a convenience copy of public sources. Always verify against the authoritative URL in [`data/sources.json`](data/sources.json).

---

## Get the data

Three ways in, from zero-effort to fully reproducible.

**1. Python, one line (Hugging Face):**
```python
from datasets import load_dataset
ds = load_dataset("GauravGurjar/open-regulatory-corpus")["train"]
fda = ds.filter(lambda x: x["framework_id"] == "FDA-AI-MD")   # 80 chunks
```

**2. Download a release (no account, no crawler):**
```bash
# Silver only — the cleaned chunks (~1.6 MiB)
curl -L -O https://github.com/dataengineergaurav/open-regulatory-corpus/releases/latest/download/open-regulatory-silver-*.parquet

# Or the full Bronze landing zone (~43 MB of raw PDFs + HTML + headers)
curl -L -O https://github.com/dataengineergaurav/open-regulatory-corpus/releases/latest/download/open-regulatory-bronze-*.tar.gz
```
Every release ships a `SHA256SUMS` file alongside the artifacts.

**3. Run the whole pipeline yourself (from source):**
```bash
pixi install
pixi run pipeline run_id=2026-09-01
# crawl → verify-bronze → build-silver → verify-silver
```
Artifacts land in `data/bronze/<run_id>/raw/` (58 files) and `data/silver/compliance_chunks.parquet`.

---

## What's inside

38 public frameworks across five domains, plus 8 paywalled standards recorded as `skipped_public_only`.

| Domain | Frameworks |
|---|---|
| **AI Governance** (9) | NIST-AI-RMF, NIST-AI-600-1, EU-AI-ACT\*, OMB-M25-21, OMB-M25-22, OWASP-LLM-2026, CO-AI, TX-TRAIGA, SG-MODEL-AI |
| **Privacy & Data** (8) | GDPR\*, CCPA-CPRA, FERPA, COPPA, UK-DP-AI, BR-LGPD\*, AU-PRIVACY-AI, DOJ-DSP |
| **Cybersecurity** (7) | NIST-CSF2, NIST-800-53, NIST-800-171, FEDRAMP, CMMC\*, CJIS-6.1, IRS-1075 |
| **Financial** (6) | SOX, GLBA, NYDFS-500, FRB-MRM-2026, ECOA-REG-B, NAIC-AI |
| **Health / Access / Trade** (8) | HIPAA\*, HHS-PART2\*, SECTION-508, ONC-HTI1, FDA-AI-MD, NYC-LL144, IL-AIVIA\*, EAR |

`*` = **tracked but 0 chunks in the current Silver.** These are not missing by accident — see [the honest gaps](#the-honest-gaps) below.

**Skipped, by design (paywalled, 8):** ISO 42001 / 42005 / 23894 / 38507 / 5338 / 24028, SOC 2, PCI-DSS.

---

## The honest gaps

Data work is mostly about what *didn't* land, and pretending otherwise makes a corpus untrustworthy. Seven of the 38 public frameworks currently produce **zero chunks**, and each has a documented cause:

| Framework | Why it's empty |
|---|---|
| `GDPR`, `EU-AI-ACT` | EUR-Lex serves a JavaScript shell (~2 KB) instead of the regulation text |
| `HIPAA`, `HHS-PART2`, `CMMC` | WAF returned HTTP 403 (Akamai) |
| `IL-AIVIA` | Request timed out |
| `BR-LGPD` | The "PDF" URL actually returns an HTML wrapper page |

Two more land as raw bytes but extract to noise: `HIPAA`-class WAF challenge pages (`AwsWaf`, "JavaScript is disabled") are filtered in the Silver stage, and the `BR-LGPD` wrapper is dropped as navigation chrome. The full remediation playbook lives in [`docs/DATA_PIPELINE.md`](docs/DATA_PIPELINE.md#troubleshooting). **Gaps are tracked as data, not hidden** — recovering one is a measurable win release-over-release.

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
  └─────────────┘                          └────┬─────┘  58 files · 43 MB
        │                                       │
        │                                       │  trafilatura (HTML) + PyMuPDF (PDF)
        │                                       │  dedup by sha256 · chunk 512 / 50
        │                                       ▼
        │                                  ┌───────────┐
        │                                  │  SILVER   │  compliance_chunks.parquet
        │                                  └─────┬─────┘  1,519 chunks · 54 docs
        │                                        │
        ▼                                        ▼
   monthly GitHub Release  ◀────────── publish ──────────▶  Hugging Face dataset
   (bronze tar + silver parquet + SHA256SUMS)
```

**Bronze — full raw landing (`data/bronze/<run_id>/`)**
Verbatim bytes, never mutated. Files are named by *magic bytes*, not by URL guessing (a `.pdf` URL that returns HTML is stored as `.html` — the extension never lies). A `manifest.jsonl` records what happened to every source; `headers/<ID>.json` preserves the HTTP response; `scrapy_stats.json` captures crawl telemetry. `latest` is a symlink to the newest run.

**Silver — cleaned + chunked (`data/silver/compliance_chunks.parquet`)**
HTML is extracted with `trafilatura` (with a tag-strip fallback for stubborn pages); PDFs with PyMuPDF, page-tagged so you never lose the page reference. Documents are deduplicated by content hash, split into 512-token windows with 50 tokens of overlap (≈384 words per chunk), then written to Parquet via `datasets`.

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

<!-- sync:stats -->
Measured from `data/silver/compliance_chunks.parquet` (run `2026-09-01_1903`):

- **1,519** chunks across **54** documents, spanning **31 of 38** public frameworks
- **~763,236** estimated tokens of compliance text
- **1,236** PDF chunks / **283** HTML chunks
- **384**-word median chunk length
- Largest documents: **CJIS-6.1** (466), **IRS-1075** (228), **SOX** (226), **CCPA-CPRA** (126)
- Bronze: **58** raw files (**27** PDF · **31** HTML, **43** MB); manifest **58** ok · **8** skipped · **4** error
<!-- /sync:stats -->

> The top three documents alone are ~55% of all chunks. That's a real characteristic of regulatory text (CJIS and SOX are enormous), and something to weight for when sampling.

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
│   ├── verify_bronze.py      asserts manifest/raw/header invariants
│   ├── verify_silver.py      asserts Silver row count + schema
│   ├── verify_sources.py     reports per-source acquisition health (gaps)
│   ├── detect_drift.py       diffs two Bronze runs by raw hash (drift report)
│   ├── publish_hf.py         uploads Silver + card to Hugging Face
│   └── sync_published.py     keeps README / HF card / GitHub About in sync
├── data/
│   ├── sources.json          the single source of truth: 46 sources, 38 public
│   ├── bronze/               raw landing zone (raw/ + headers/ are Release assets)
│   └── silver/               compliance_chunks.parquet + silver_stats.json
├── notebooks/                01_search · 02_silver_eda · 03_silver_analysis
├── docs/                     you are (one level) here
├── .commandcode/skills/      agent skills — compliance-officer (audit · research · proposals)
├── .github/workflows/        ci.yml + monthly-release.yml
└── pixi.toml                 environment + named tasks (crawl, build-silver, pipeline…)
```

---

## How it stays fresh

A scheduled GitHub Action runs on the **1st of every month**: it crawls, verifies Bronze, builds and verifies Silver, packages the artifacts, cuts a GitHub Release with a `SHA256SUMS`, and publishes to Hugging Face. Every run is identified by a `run_id` (e.g. `2026-09-01_1903`), and Bronze keeps every run side-by-side, so history is never overwritten.

Want to add a framework? Add one object to [`data/sources.json`](data/sources.json) and open a PR — the spider is fully data-driven. See [`docs/ARCHITECTURE.md#extending-the-corpus`](docs/ARCHITECTURE.md#extending-the-corpus).

---

## License & disclaimer

- **Code:** [MIT](LICENSE)
- **Data:** CC-BY-4.0 where applicable — source documents retain their original terms.
- **Not legal advice.** This is a research and engineering artifact, not a compliance guarantee. Verify against the authoritative source for every framework.

Every source URL, with its public/paywalled status, is enumerated in [`data/sources.json`](data/sources.json).
