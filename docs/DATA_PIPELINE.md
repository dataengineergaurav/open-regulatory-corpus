# Data Pipeline — Bronze → Silver (public-only, retain raw + all PDFs)

**Status:** Data-only (no Gold/LLM). Public 38 → Bronze 58 raw (27 true PDFs) → Silver 1519 chunks (clean, 54 docs) — patched 2026-09-01 (WAF/nav filtered, dedup).
**Deps:** `pixi.toml` `scrapy>=2.18`, `trafilatura>=2.0`, `pymupdf>=1.28`, `datasets==2.20.0`, `torch==2.3.1` (chapter10 pattern)
**Design:** `docs/superpowers/specs/2026-09-01-compliance-data-only-design.md` | **Leadership:** `docs/reports/2026-09-01-compliance-leadership-report.html`

## Medallion

### Bronze — full raw landing (keep-all)
```
data/bronze/<run_id>/
  raw/<ID>.html | <ID>.pdf | <ID>_pdfN.pdf   # 58 files, 44M latest
  headers/<ID>.json                          # final_url, status, content_type, bytes, fetched_at
  manifest.jsonl                             # 70 lines: 58 ok + 8 skipped + 4 error
  scrapy_stats.json
data/bronze/latest -> <run_id>
data/sources.json                            # 46: 38 public + 8 skipped (ISO×6 + SOC2 + PCI-DSS)
```
- `raw/` verbatim bytes, magic-byte ext (`pipelines.py:31`), `latest` symlink on `close_spider`.
- `manifest.jsonl` auditable: `ok` (bytes, sha256_raw), `skipped_public_only` (paywalled), `error` (WAF 403 / timeout).
- WAF-blocked 4: `HIPAA`, `HHS-PART2`, `CMMC`, `IL-AIVIA` (Akamai) — log only, no retry storm.

### Silver — cleaned + chunked (training-ready) — patched 2026-09-01_1910
```
data/silver/compliance_chunks.parquet   # 1519 rows, 1.7M, 54 docs (was 1556/57 before WAF/nav fix)
data/silver/silver_stats.json           # {run_id, chunks:1519, docs:54}
scripts/build_silver.py                 # trafilatura (html) + fitz (pdf) → word-split 512/50 → datasets.to_parquet() + WAF/nav filter + sha dedup
scripts/verify_bronze.py                # 58 ok / 8 skipped / 4 error, raw==headers allowed dup CJIS
scripts/verify_silver.py                # >=300 chunks (1519 clean, 0 WAF, 0 dup chunk_id)
```
- Schema: `framework_id, chunk_id ({ID}-{idx}), text, source (bronze raw path), kind (html/pdf), token_est (words*1.33), sha256`
- Distribution: `FDA-AI-MD 80`, `EAR 52`, `FERPA 39`, `AU-PRIVACY-AI 38`, `OMB-M25-21 29`, etc. `EU-AI-ACT 0`, `GDPR 0` (WAF challenge removed), `BR-LGPD 0` (nav wrapper removed — true 1.2M PDF needs mirror).
- Dedup by full-doc sha256 (`CJIS-6.1_pdf1` duplicate removed), `CJIS-6.1` html (2) vs `CJIS-6.1_pdf` (462) disambiguated via `seen_iid` → no `dup chunk_id`.

## Run
```bash
# Bronze
pixi run scrapy crawl compliance -a run_id=2026-09-01_1910
pixi run python scripts/verify_bronze.py   # BRONZE OK

# Silver
pixi run python scripts/build_silver.py
pixi run python scripts/verify_silver.py   # SILVER OK (1556 rows)
```

## Sources (38 public in Bronze, 8 skipped)
**In (38):** NIST-AI-RMF, NIST-AI-600-1, NIST-CSF2.pdf, NIST-800-53, FEDRAMP, EU-AI-ACT, GDPR, HIPAA (WAF), GLBA, FERPA, CCPA-CPRA, CO-AI, TX-TRAIGA, OMB-M25-21.pdf, OMB-M25-22.pdf, OWASP-LLM-2026, SOX, NIST-800-171, CMMC (WAF), CJIS-6.1.pdf, IRS-1075, SECTION-508, HHS-PART2 (WAF), ONC-HTI1, FDA-AI-MD, FRB-MRM-2026, NYDFS-500, ECOA-REG-B, NAIC-AI, COPPA, NYC-LL144, IL-AIVIA (WAF), UK-DP-AI, BR-LGPD.pdf (HTML wrapper), AU-PRIVACY-AI, SG-MODEL-AI, DOJ-DSP, EAR — plus 22 secondary PDFs discovered (e.g., `CCPA-CPRA_pdf1.pdf` 1.9M, `NIST-800-53_pdf2.pdf` 93K).

**Out (8):** ISO-42001, ISO-42005, ISO-23894, ISO-38507, ISO-5338, ISO-24028, SOC2, PCI-DSS (paywalled, no partial).

## PDF inventory (latest `2026-09-01_1910`, 44M)
- **Direct PDFs (5):** NIST-CSF2, OMB-M25-21/22, BR-LGPD, CJIS-6.1 (CJIS fixed `/view` → 4.2M true PDF 473p 159K words)
- **True PDFs on disk (27):** 3 direct + 22 secondary + 2 CJIS (html+pdf disambiguated). `BR-LGPD.pdf` in Bronze is 217K HTML wrapper — true 1.2M PDF not yet landed (nav filtered in Silver, so 0 chunks). `CJIS-6.1` html (2) vs `CJIS-6.1_pdf` (462) now distinct.
- Check: `ls data/bronze/latest/raw/*.pdf | wc -l` (27), `grep -c application/pdf data/bronze/latest/manifest.jsonl` (27), Silver `pdf:1236 / html:318` (was 1236/320 before WAF filter).

## Troubleshooting
- `HHS`/`business.defense.gov` 403: Akamai WAF, not robots.txt. Add mirror `hhs.gov/guidance` / `dodcio.defense.gov/cmmc` to `data/sources.json` as alias.
- `eur-lex` 2K truncated: `?displayAll=true` still JS shell. Fetch `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:32024R1689` before Gold.
- `BR-LGPD` HTML wrapper: gov.br page links to PDF via JS, not `<a href$=.pdf>`. Add direct `https://www.gov.br/.../lgpd-en-lei-no-13-709.pdf` manually.
- `verify_bronze` hdr vs raw off by 1: `CJIS-6.1.html` + `.pdf` share stem → header collision, allowed (`abs(raw-hdr)<=1`).

## Next (deferred per data-only scope)
- Gold: `all-MiniLM-L6-v2` MNRL fine-tune (chapter10 pattern, `BATCH=8` MPS) → FAISS recall@3 ≥0.80
- No `.gitignore` change per user ask — `data/` tracked, keep-all runs will grow (~44M/run).
