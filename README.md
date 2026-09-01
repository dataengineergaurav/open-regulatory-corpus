# Compliance Data — Bronze → Silver (public-only, retain raw + all PDFs)

Moved from `hands-on-llm-book-jay-alammar` data engineering work to `passion-projects/compliance-data`.

**Layout:** `data/` (bronze/silver/sources.json) + `scraper/` (Scrapy) + `scripts/` + `docs/` — see `docs/DATA_PIPELINE.md`.

**Quick start:**
```bash
pixi install
pixi run scrapy crawl compliance -a run_id=2026-09-01_1910
pixi run python scripts/verify_bronze.py
pixi run python scripts/build_silver.py
pixi run python scripts/verify_silver.py
```
