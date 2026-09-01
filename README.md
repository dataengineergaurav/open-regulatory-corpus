# Compliance Data — Bronze → Silver (public-only, retain raw + all PDFs)

Moved from `hands-on-llm-book-jay-alammar` data engineering work to `passion-projects/compliance-data`.

**Layout:** `data/` (bronze/silver/sources.json) + `scraper/` (Scrapy) + `scripts/` + `docs/` — see `docs/DATA_PIPELINE.md`.

**Quick start (local):**
```bash
pixi install
# from scraper/ (scrapy.cfg lives there) — or use pixi task:
pixi run crawl run_id=2026-09-01_1910
# equivalent: cd scraper && pixi run scrapy crawl compliance -a run_id=2026-09-01_1910

pixi run verify-bronze   # or: pixi run python scripts/verify_bronze.py
pixi run build-silver    # or: pixi run python scripts/build_silver.py
pixi run verify-silver
# full: pixi run pipeline run_id=2026-09-01_1910
```

**GitHub autonomous:**
- `CI` (.github/workflows/ci.yml:1) — on push/PR, `pixi install` + `verify_silver` (bronze raw is Release asset, not in git).
- `Monthly Dataset Release` (.github/workflows/monthly-release.yml:1) — cron `0 2 1 * *` (1st 02:00 UTC) + manual `workflow_dispatch`. Does crawl → verify_bronze → build_silver → verify_silver → `compliance-bronze-<date>.tar.gz` + `compliance-silver-<date>.parquet/.zip` → GitHub Release `bronze-silver-YYYY-MM-DD` with `SHA256SUMS.txt`.
- Repo: https://github.com/dataengineergaurav/compliance-data — Releases: https://github.com/dataengineergaurav/compliance-data/releases

**Releases (monthly, autonomous):**
```bash
gh release view bronze-silver-2026-09-01 --json assets --jq '.assets[].name'
# or trigger now:
gh workflow run "Monthly Dataset Release" --ref main
# with custom id:
gh workflow run "Monthly Dataset Release" --ref main --field run_id=2026-09-15
```

**Storage:** `data/bronze/*/raw` (44M/run) excluded from git via `.gitignore:22` — shipped as Release `tar.gz` (GitHub limit 2GB/file, repo stays <100M). `data/silver/*.parquet` (1.6M) + `manifest.jsonl`/`scrapy_stats.json` tracked for audit. To track raw in git instead, comment out those `.gitignore` lines.
