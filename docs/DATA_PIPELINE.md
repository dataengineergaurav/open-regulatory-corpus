# Data Pipeline — Bronze → Silver

The operational runbook. For *why* the stages exist and how the components fit, read [`ARCHITECTURE.md`](ARCHITECTURE.md). For field-level detail, see [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md).

**Status:** 38 public → Bronze 58 raw (27 PDFs + 31 HTML, 43 MB) → Silver 1,519 chunks (54 docs), run `2026-09-01_1903` — WAF/nav filtered, deduped.
**Deps:** `pixi.toml` — `scrapy>=2.18`, `trafilatura>=2.0`, `pymupdf>=1.28`, `datasets==2.20.0`.

---

## Medallion

### Bronze — full raw landing

```
data/bronze/<run_id>/
  raw/<ID>.html | <ID>.pdf | <ID>_pdfN.pdf   # 58 files, 43 MB
  headers/<ID>.json
  manifest.jsonl                             # 70 lines: 58 ok + 8 skipped + 4 error
  scrapy_stats.json
data/bronze/latest -> <run_id>
data/sources.json                            # 46: 38 public + 8 skipped (ISO×6 + SOC2 + PCI-DSS)
```

- `raw/` holds verbatim bytes; the extension comes from **magic bytes first** (`pipelines.py`), so a `.pdf` URL that returns HTML is stored as `.html`.
- `manifest.jsonl` records one of three outcomes per source: `ok` (with `bytes`, `sha256_raw`), `skipped_public_only` (paywalled), or `error` (WAF 403 / timeout).
- `latest` is repointed to the newest run on `close_spider`.
- WAF-blocked (4): `HIPAA`, `HHS-PART2`, `CMMC`, `IL-AIVIA` (Akamai) — recorded, not hidden.

### Silver — cleaned + chunked

```
data/silver/compliance_chunks.parquet   # 1,519 rows, ~1.6 MiB, 54 docs
data/silver/silver_stats.json           # {run_id, chunks:1519, docs:54}
scripts/build_silver.py                 # trafilatura + PyMuPDF → 512/50 → datasets.to_parquet()
```

- **Schema:** `framework_id, chunk_id ({ID}-{idx}), text, source, kind, token_est (words×1.33), sha256`
- **Extraction:** HTML via `trafilatura` (with a tag-strip fallback under 500 chars); PDF via PyMuPDF, page-tagged `[Page N]`.
- **Filtering:** drops WAF challenge pages (`AwsWaf`, "JavaScript is disabled"), the `BR-LGPD` nav wrapper, and anything under 200 chars.
- **Dedup:** by `sha256` of the extracted text. `CJIS-6.1` html + pdf share a stem and are disambiguated via `seen_iid`.
- **Distribution:** `kind` = 1,236 pdf / 283 html. Largest stems: `CJIS-6.1` 466, `IRS-1075` 228, `SOX` 226, `CCPA-CPRA` 126, `EAR` 84, `FDA-AI-MD` 80.
- **Empty (0 chunks):** `EU-AI-ACT`, `GDPR` (EUR-Lex JS shell), `CMMC`, `HIPAA`, `HHS-PART2`, `IL-AIVIA` (WAF/timeout), `BR-LGPD` (nav wrapper). See [Troubleshooting](#troubleshooting).

---

## Run

```bash
pixi run pipeline run_id=2026-09-01          # full Bronze → Silver
```

Or stepwise:

```bash
pixi run crawl run_id=2026-09-01
pixi run verify-bronze
pixi run build-silver
pixi run verify-silver
```

| Task | Command | Does |
|---|---|---|
| `crawl` | `python -m scrapy crawl compliance -a run_id=…` | Fetch all `public` sources into Bronze |
| `verify-bronze` | `python scripts/verify_bronze.py` | Assert manifest/raw/header invariants |
| `build-silver` | `python scripts/build_silver.py` | Extract, dedup, chunk → Parquet |
| `verify-silver` | `python scripts/verify_silver.py` | Assert Silver exists with a plausible row count |
| `verify-sources` | `python scripts/verify_sources.py` | Report per-source acquisition health (healthy / empty / error) |
| `detect-drift` | `python scripts/detect_drift.py` | Diff the newest Bronze run against the previous one by `sha256_raw` |
| `verify` | all three verifiers | `verify-bronze && verify-silver && verify-sources` |
| `pipeline` | all four, chained | End-to-end |

The verifiers are also wired into CI (`.github/workflows/ci.yml`) and the monthly release (`.github/workflows/monthly-release.yml`), so a broken run fails before it publishes.

---

## Publishing & keeping surfaces in sync

The same numbers appear in three published places — `README.md`, the Hugging Face dataset card, and the GitHub "About" box. Rather than let them drift by hand, `scripts/sync_published.py` derives them from the artifacts and rewrites them:

```bash
pixi run check-docs        # CI: exit 1 if README/HF card numbers are stale
pixi run sync-published    # rewrite regions + update GitHub About + push HF card
```

- Only text between `<!-- sync:* -->` markers is generated; surrounding prose stays hand-written.
- `sync-published` is **idempotent** — it writes or commits only when something changed — and **degrades gracefully**: a GitHub permission failure warns but never blocks the release.
- CI runs `check-docs` on every push/PR; the monthly release runs `sync-published` after publishing (needs `secrets.HF_TOKEN`; GitHub About also needs a token with repo-metadata scope, e.g. `secrets.REPO_ADMIN_TOKEN`).

---

## Sources (38 in, 8 skipped)

**In (38):** NIST-AI-RMF, NIST-AI-600-1, NIST-CSF2.pdf, NIST-800-53, FEDRAMP, EU-AI-ACT, GDPR, HIPAA (WAF), GLBA, FERPA, CCPA-CPRA, CO-AI, TX-TRAIGA, OMB-M25-21.pdf, OMB-M25-22.pdf, OWASP-LLM-2026, SOX, NIST-800-171, CMMC (WAF), CJIS-6.1.pdf, IRS-1075, SECTION-508, HHS-PART2 (WAF), ONC-HTI1, FDA-AI-MD, FRB-MRM-2026, NYDFS-500, ECOA-REG-B, NAIC-AI, COPPA, NYC-LL144, IL-AIVIA (WAF), UK-DP-AI, BR-LGPD.pdf (HTML wrapper), AU-PRIVACY-AI, SG-MODEL-AI, DOJ-DSP, EAR — plus 22 secondary PDFs.

**Out (8):** ISO-42001, ISO-42005, ISO-23894, ISO-38507, ISO-5338, ISO-24028, SOC2, PCI-DSS (paywalled).

---

## PDF inventory

- **Direct PDFs (5):** NIST-CSF2, OMB-M25-21/22, BR-LGPD, CJIS-6.1 (`/view` → 4.2 MB true PDF).
- **True PDFs on disk (27):** 3 direct + 22 secondary + 2 CJIS. `BR-LGPD.pdf` is an HTML wrapper (the true 1.2 MB PDF was not landed).

---

## Troubleshooting

- **`HHS` / `business.defense.gov` 403:** Akamai WAF. Add a mirror — `hhs.gov/guidance` or `dodcio.defense.gov/cmmc`.
- **`eur-lex` ~2 KB truncated:** `?displayAll=true` still returns a JS shell. Fetch `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:32024R1689`.
- **`BR-LGPD` HTML wrapper:** the PDF link is JS-generated, not an `<a href$=.pdf>`. Add the direct PDF manually.
- **`CJIS-6.1` viewer URL:** `/view` serves an HTML viewer; the spider re-requests without `/view` to get the true PDF.
- **`verify_bronze` header/raw off by one:** `CJIS-6.1.html` and `CJIS-6.1.pdf` share a stem, so the check allows `abs(raw − headers) <= 1`.
- **A framework yields 0 chunks:** check `manifest.jsonl` for its `status` (`error` = WAF/timeout, `ok` but 0 chunks = served a shell or filtered at extraction). Prefer adding an authoritative `mirrors` entry in `sources.json` (an alternate surface that serves the text) over mutating Bronze or adding extraction filters.

---

## Related

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — design, data flow, decisions, extension points
- [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md) — every artifact and field
- [`FAQ.md`](FAQ.md#why-are-some-frameworks-empty) — why the gaps exist
