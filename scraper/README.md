# Compliance Scraper — Bronze (public-only, retain raw + all PDFs) — patched 2026-09-01_1910

**Current:** `data/bronze/latest` → `2026-09-01_1910` (58 ok + 8 skipped + 4 error =70 manifest, 44M) → Silver 1519 clean (54 docs, 0 WAF/nav).

Scrapy spider that lands **38 public** `Primary source` URLs from `data/sources.json` (46 total = 38 public + 8 skipped ISO/SOC2/PCI-DSS) to immutable Bronze, then discovers secondary PDFs linked from those pages.

## Layout
```
data/sources.json                          # 46 rows: id, url, public flag
data/bronze/<run_id YYYY-MM-DD_HHMM>/
  raw/<ID>.html | <ID>.pdf | <ID>_pdfN.pdf # verbatim bytes (58 files in latest)
  headers/<ID>.json                        # final_url, status, content-type, fetched_at, bytes
  manifest.jsonl                           # 70 lines: 58 ok + 8 skipped_public_only + 4 error (HHS/CMMC/IL-AIVIA WAF)
  scrapy_stats.json
data/bronze/latest -> <run_id>             # symlink
scraper/
  scrapy.cfg
  compliance_scraper/settings.py           # ROBOTSTXT_OBEY, AUTOTHROTTLE=2, HTTPCACHE 7d
  compliance_scraper/spiders/generic.py    # start_requests + PDF discovery (up to 2 per HTML, CJIS /view fix)
  compliance_scraper/pipelines.py          # RawPipeline: magic-byte ext, manifest, headers, latest symlink
```

## Setup
```bash
pixi add scrapy trafilatura pymupdf   # already in pixi.toml
pixi install
```

## Run
```bash
# Bronze — single-page fetch + up to 2 linked PDFs per HTML (same-host, href ends .pdf)
pixi run scrapy crawl compliance -a run_id=2026-09-01_1910 -s LOG_LEVEL=INFO
# or without run_id (auto YYYY-MM-DD_HHMM):
pixi run scrapy crawl compliance

# Verify
pixi run python scripts/verify_bronze.py  # expects 58 ok / 8 skipped / 4 error, 58 raw
```

## PDF handling
- Ext by **magic (`%PDF`) + content-type**, not URL suffix — fixes `BR-LGPD.pdf` (actually HTML) and `CJIS-6.1` viewer (`/view` → true PDF `.../cjis_security_policy_v6-1_20260625.pdf` 4.2M)
- Secondary PDFs: for each HTML `text/html`, follows up to 2 `<a href="*.pdf">` on same host (`generic.py:47`). Social-share `?pdf` query links ignored (must end `.pdf` path).
- BR-LGPD true 1.2M PDF still lands as HTML (gov.br wraps PDF behind JS) — no `*.pdf` href to follow, will stay 1 chunk until mirror added.

## Notes
- Keep-all runs: `data/bronze/20*` retained per user ask, `latest` symlink points to newest. `HTTPCACHE` 7d avoids re-fetching 304.
- WAF-blocked 4 (HIPAA, HHS-PART2, CMMC, IL-AIVIA) are `error` in manifest — Akamai 403/timeout, recover via mirror URLs if needed.
- No ISO/SOC2/PCI-DSS fetches — `skipped_public_only` (paywalled, no partial per spec).
- Design: `docs/superpowers/specs/2026-09-01-compliance-data-only-design.md`
- Leadership report: `docs/reports/2026-09-01-compliance-leadership-report.html`
