# Compliance Data — Bronze → Silver

Public-only compliance corpus: 38 sources → Bronze raw (58 files, 27 PDFs) → Silver `compliance_chunks.parquet` (1519 chunks, 512/50).

**Get data:** [Releases](https://github.com/dataengineergaurav/compliance-data/releases) — `compliance-silver-*.parquet` + `compliance-bronze-*.tar.gz` (monthly, SHA256).

**Run locally:**
```bash
pixi install
pixi run pipeline run_id=2026-09-01  # crawl → verify_bronze → build_silver → verify_silver
# stepwise: pixi run crawl run_id=... && pixi run verify-bronze && pixi run build-silver && pixi run verify-silver
```

**Docs:** `docs/DATA_PIPELINE.md` · **Sources:** `data/sources.json` · **Releases:** `https://github.com/dataengineergaurav/compliance-data/releases`
