# Compliance Data-Only Ingest — Design Spec (2026-09-01)

**Status:** Approved (plan → build 2026-09-01)
**Scope:** Data-only (Bronze + Silver), public-only 38 sources, no embeddings/RAG/KG, retain all raw on disk, keep all `run_id`.

## Goal
Land verifiable dataset for the 50-row compliance table (ID / Framework / Type / Scope / Focus / Baseline priority / Rule vs Evidence themes / Primary source) to disk, public sources only, with full raw retention for replay/audit. Silver output feeds future fine-tune but no LLM work in this phase.

## Non-Goals
- No embeddings, FAISS, generative training, RAG, KG, ISO paywall bypass
- No delta/lakehouse, no Playwright until proven needed

## Data Sources
- **IN (38 fetched):** NIST-AI-RMF, NIST-AI-600-1, NIST-CSF2 (PDF), NIST-800-53, FEDRAMP, EU-AI-ACT, GDPR, HIPAA, GLBA, FERPA, CCPA-CPRA, CO-AI, TX-TRAIGA, OMB-M25-21 (PDF), OMB-M25-22 (PDF), OWASP-LLM-2026, SOX, NIST-800-171, CMMC, CJIS-6.1 (PDF), IRS-1075, SECTION-508, HHS-PART2, ONC-HTI1, FDA-AI-MD, FRB-MRM-2026, NYDFS-500, ECOA-REG-B, NAIC-AI, COPPA, NYC-LL144, IL-AIVIA, UK-DP-AI, BR-LGPD (Brazil gov.br PDF), AU-PRIVACY-AI, SG-MODEL-AI (PDPC PDF variant), DOJ-DSP, EAR
- **OUT (8 never requested, `skipped_public_only`):** ISO-42001, ISO-42005, ISO-23894, ISO-38507, ISO-5338, ISO-24028, SOC2, PCI-DSS (full PDF gated; no HTML stub per no-partial rule)

## Medallion Layout (file-based, keep all runs)
```
data/bronze/<run_id YYYY-MM-DD_HHMM>/
  raw/<ID>.html | <ID>.pdf
  headers/<ID>.json
  manifest.jsonl   # 46 lines: 38 ok + 8 skipped
  scrapy_stats.json
data/bronze/latest -> <run_id>/  # symlink
data/silver/
  compliance_clean.parquet
  compliance_chunks.parquet  # 512 tok / 50 overlap, sha256 dedup, ~5.3k chunks
```
No `data/gold/` in this phase. No `.gitignore` change per user ask.

## Scrapy Design
- `pixi add scrapy trafilatura pymupdf` — single spider `scraper/compliance_scraper/spiders/generic.py` reads `data/sources.json` (derived from table) filtered to 38.
- `RawPipeline` writes `raw/` + `headers/` on 200 before cleaning. `ROBOTSTXT_OBEY=True, AUTOTHROTTLE_ENABLED=True, TARGET_CONCURRENCY=2, CONCURRENT_REQUESTS=4, DOWNLOAD_DELAY=1.0, RETRY_TIMES=2, HTTPCACHE_ENABLED=True`.
- Eur-lex EU-AI-ACT/GDPR: try `?displayAll=true` equivalent; if `len(text)<5k` flag `needs_review` in manifest, no Playwright.

## Silver Build
`scripts/build_silver.py <run_id>` reads `latest/raw/*` → trafilatura/pymupdf → clean (keep h1-h3 as `section`, `page` for PDFs) → dedup by sha256 → chunk 512/50 via sentence-transformers tokenizer → `datasets.Dataset.to_parquet()`.

## Quality Gates
- `verify_bronze`: 38 raw + 38 headers + 46 manifest lines, `bytes>0`, no duplicate `sha256_raw`.
- `verify_silver`: 5k-5.5k chunks, avg 350-512 tok, spot-check EU-AI-ACT Annex.

## Execution Milestones
1) Scaffold scraper + sources.json
2) Scrape 38 → Bronze
3) Build Silver → verify
Deferred: embeddings/FAISS, KG, Delta — promote on eval miss.

## Risks
- Eur-lex pagination truncation → mitigated by `?displayAll` + manifest `truncated` flag.
- JS apps (CMMC, content.naic) returning empty shell → flagged `js_required` for second pass.
- PDF scan 10MB limit → skip oversized, log in manifest.
