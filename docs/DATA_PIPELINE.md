# Data Pipeline — Bronze → Silver (public-only, retain raw + all PDFs)

**Status:** 38 public → Bronze 58 raw (27 PDFs, 44M) → Silver 1519 chunks (54 docs) — patched 2026-09-01 (WAF/nav filtered, dedup).
**Deps:** `pixi.toml` `scrapy>=2.18`, `trafilatura>=2.0`, `pymupdf>=1.28`, `datasets==2.20.0`

## Medallion

### Bronze — full raw landing
```
data/bronze/<run_id>/
  raw/<ID>.html | <ID>.pdf | <ID>_pdfN.pdf   # 58 files, 44M
  headers/<ID>.json
  manifest.jsonl                             # 70 lines: 58 ok + 8 skipped + 4 error
  scrapy_stats.json
data/bronze/latest -> <run_id>
data/sources.json                            # 46: 38 public + 8 skipped (ISO×6 + SOC2 + PCI-DSS)
```
- `raw/` verbatim bytes, magic-byte ext (`pipelines.py:31`), `latest` symlink on `close_spider`.
- `manifest.jsonl`: `ok` (bytes, sha256_raw), `skipped_public_only` (paywalled), `error` (WAF 403 / timeout).
- WAF-blocked 4: `HIPAA`, `HHS-PART2`, `CMMC`, `IL-AIVIA` (Akamai) — log only.

### Silver — cleaned + chunked
```
data/silver/compliance_chunks.parquet   # 1519 rows, 1.7M, 54 docs
data/silver/silver_stats.json           # {run_id, chunks:1519, docs:54}
scripts/build_silver.py                 # trafilatura + fitz → 512/50 → datasets.to_parquet()
```
- Schema: `framework_id, chunk_id ({ID}-{idx}), text, source, kind, token_est (words*1.33), sha256`
- Distribution: `FDA-AI-MD 80`, `EAR 52`, `FERPA 39`, `AU-PRIVACY-AI 38`, etc. `EU-AI-ACT 0`, `GDPR 0` (WAF filtered), `BR-LGPD 0` (nav wrapper filtered).
- Dedup by sha256, `CJIS-6.1` html/pdf disambiguated via `seen_iid`.

## Run
```bash
pixi run pipeline run_id=2026-09-01          # full Bronze→Silver
# stepwise:
pixi run crawl run_id=2026-09-01
pixi run verify-bronze
pixi run build-silver
pixi run verify-silver
```

## Sources (38 in, 8 skipped)

**In (38):** NIST-AI-RMF, NIST-AI-600-1, NIST-CSF2.pdf, NIST-800-53, FEDRAMP, EU-AI-ACT, GDPR, HIPAA (WAF), GLBA, FERPA, CCPA-CPRA, CO-AI, TX-TRAIGA, OMB-M25-21.pdf, OMB-M25-22.pdf, OWASP-LLM-2026, SOX, NIST-800-171, CMMC (WAF), CJIS-6.1.pdf, IRS-1075, SECTION-508, HHS-PART2 (WAF), ONC-HTI1, FDA-AI-MD, FRB-MRM-2026, NYDFS-500, ECOA-REG-B, NAIC-AI, COPPA, NYC-LL144, IL-AIVIA (WAF), UK-DP-AI, BR-LGPD.pdf (HTML wrapper), AU-PRIVACY-AI, SG-MODEL-AI, DOJ-DSP, EAR — plus 22 secondary PDFs.

**Out (8):** ISO-42001, ISO-42005, ISO-23894, ISO-38507, ISO-5338, ISO-24028, SOC2, PCI-DSS (paywalled).

## PDF inventory (latest, 44M)
- **Direct PDFs (5):** NIST-CSF2, OMB-M25-21/22, BR-LGPD, CJIS-6.1 (`/view` → 4.2M)
- **True PDFs on disk (27):** 3 direct + 22 secondary + 2 CJIS. `BR-LGPD.pdf` is HTML wrapper (true 1.2M PDF not landed).

## Troubleshooting
- `HHS`/`business.defense.gov` 403: Akamai WAF. Add mirror `hhs.gov/guidance` / `dodcio.defense.gov/cmmc`.
- `eur-lex` 2K truncated: `?displayAll=true` still JS shell. Fetch `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:32024R1689`.
- `BR-LGPD` HTML wrapper: JS link, not `<a href$=.pdf>`. Add direct PDF manually.
- `verify_bronze` hdr vs raw off by 1: `CJIS-6.1.html` + `.pdf` share stem → allowed `abs(raw-hdr)<=1`.
