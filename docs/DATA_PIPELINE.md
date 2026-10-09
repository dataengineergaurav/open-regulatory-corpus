# Data Pipeline — Bronze → Silver

The operational runbook. For *why* the stages exist and how the components fit, read [`ARCHITECTURE.md`](ARCHITECTURE.md). For field-level detail, see [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md).

**Status:** 38 public → Bronze 57 raw (25 PDFs + 32 HTML, 46 MB) → Silver 2,041 chunks (54 docs), run `2026-10-09` — WAF/nav filtered, deduped.
**Deps:** `pixi.toml` — `scrapy>=2.18`, `trafilatura>=2.0`, `pymupdf>=1.28`, `datasets==2.20.0`.

---

## Medallion

### Bronze — full raw landing

```
data/bronze/<run_id>/
  raw/<ID>.html | <ID>.pdf | <ID>_pdfN.pdf   # 57 files, 46 MB
  headers/<ID>.json
  manifest.jsonl                             # 68 lines: 57 ok + 8 skipped + 3 error
  scrapy_stats.json
data/bronze/latest -> <run_id>
data/sources.json                            # 46: 38 public + 8 skipped (ISO×6 + SOC2 + PCI-DSS)
```

- `raw/` holds verbatim bytes; the extension comes from **magic bytes first** (`pipelines.py`), so a `.pdf` URL that returns HTML is stored as `.html`.
- `manifest.jsonl` records one of three outcomes per source: `ok` (with `bytes`, `sha256_raw`), `skipped_public_only` (paywalled), or `error` (non-200 / WAF).
- `latest` is repointed to the newest run on `close_spider`.
- Non-200 (3): `NYDFS-500`, `ECOA-REG-B`, `NAIC-AI` — recorded, not hidden.

### Silver — cleaned + chunked

```
data/silver/compliance_chunks.parquet   # 2,041 rows, ~2.0 MiB, 54 docs
data/silver/silver_stats.json           # {run_id, chunks:2041, docs:54}
scripts/build_silver.py                 # trafilatura + PyMuPDF → 512/50 → datasets.to_parquet()
```

- **Schema:** `framework_id, chunk_id ({ID}-{idx}), text, source, kind, token_est (words×1.33), sha256`
- **Extraction:** HTML via `trafilatura` (with a tag-strip fallback under 500 chars); PDF via PyMuPDF, page-tagged `[Page N]`.
- **Filtering:** drops WAF challenge pages (`AwsWaf`, "JavaScript is disabled"), the `BR-LGPD` nav wrapper, and anything under 200 chars.
- **Dedup:** by `sha256` of the extracted text. `CJIS-6.1` html + pdf share a stem and are disambiguated via `seen_iid`.
- **Section-aware chunking (opt-in):** `python scripts/build_silver.py --section-aware` splits on numbered headings (`Article 5`, `§ 164.312`, `AC-2`) when at least 3 are found, falling back to the fixed window otherwise. Default is unchanged.
- **Quality report:** each run writes `data/silver/quality_report.json` — per-document flags (`short`, `table_heavy`, `fragmented`, `low_alpha`, `garbled`) so a flattened table isn't mistaken for prose.
- **Document index:** `data/silver/index/<run_id>.json` records each document's extracted-text `sha256` — the low-noise signal `detect-drift` compares across runs (dynamic page chrome doesn't move it).
- **Balanced slice:** `build-balanced` writes `data/silver/balanced_slice.parquet` (capped per framework).
- **Distribution:** `kind` = 1,292 pdf / 749 html. Largest stems: `CJIS-6.1` 464, `IRS-1075` 228, `SOX` 226, `GDPR` 163.
- **Empty (0 chunks):** `NYDFS-500`, `ECOA-REG-B`, `NAIC-AI` (non-200), `SG-MODEL-AI` (WAF challenge), `BR-LGPD` (nav wrapper). See [Troubleshooting](#troubleshooting).

---

## Run

```bash
RUN_ID=2026-09-01 pixi run pipeline          # full Bronze → Silver
```

Or stepwise:

```bash
RUN_ID=2026-09-01 pixi run crawl
pixi run verify-bronze
pixi run build-silver
pixi run verify-silver
```

| Task | Command | Does |
|---|---|---|
| `crawl` | `RUN_ID=… pixi run crawl` | Fetch all `public` sources into Bronze |
| `verify-bronze` | `python scripts/verify_bronze.py` | Assert manifest/raw/header invariants |
| `validate-sources` | `python scripts/validate_sources.py` | Validate `data/sources.json` against its schema |
| `build-silver` | `python scripts/build_silver.py` | Extract, dedup, chunk → Parquet |
| `build-balanced` | `python scripts/build_balanced_slice.py` | Cap each framework to build `balanced_slice.parquet` |
| `verify-silver` | `python scripts/verify_silver.py` | Assert Silver exists with a plausible row count |
| `verify-sources` | `python scripts/verify_sources.py` | Report per-source acquisition health (healthy / empty / error) |
| `probe-gaps` | `python scripts/probe_gaps.py` | Re-probe the empty frameworks for usable text (used by the weekly gap watch) |
| `detect-drift` | `python scripts/detect_drift.py` | Diff the newest Bronze run against the previous one (extracted-text hash; raw fallback) |
| `build-changelog` | `python scripts/build_changelog.py` | Render a human-readable changelog (md + json) from the drift |
| `verify` | all three verifiers | `verify-bronze && verify-silver && verify-sources` |
| `pipeline` | crawl + build + verify, chained | End-to-end |

The verifiers are also wired into CI (`.github/workflows/ci.yml`) and the monthly release (`.github/workflows/monthly-release.yml`), so a broken run fails before it publishes.

---

## Publishing & keeping surfaces in sync

The same numbers appear in three published places — `README.md`, the Hugging Face dataset card, and the GitHub "About" box. Rather than let them drift by hand, `scripts/sync_published.py` derives them from the artifacts and rewrites them:

```bash
pixi run check-docs        # CI: exit 1 if README/HF card numbers are stale
pixi run sync-published    # rewrite regions + update GitHub About + push HF card
```

- Only text between `<!-- sync:* -->` markers is generated; surrounding prose stays hand-written.
- Generated regions: `headline` and `stats` (README + HF card) and `gaps` (README + HF card + `docs/FAQ.md`). The empty-framework table is computed from the artifacts, so it has one owner and can't drift.
- `sync-published` is **idempotent** — it writes or commits only when something changed — and **degrades gracefully**: a GitHub permission failure warns but never blocks the release.
- CI runs `check-docs` on every push/PR; the monthly release runs `sync-published` after publishing (needs `secrets.HF_TOKEN`; GitHub About also needs a token with repo-metadata scope, e.g. `secrets.REPO_ADMIN_TOKEN`).

---

## Sources (38 in, 8 skipped)

**In (38):** NIST-AI-RMF, NIST-AI-600-1, NIST-CSF2.pdf, NIST-800-53, FEDRAMP, EU-AI-ACT, GDPR, HIPAA, GLBA, FERPA, CCPA-CPRA, CO-AI, TX-TRAIGA, OMB-M25-21.pdf, OMB-M25-22.pdf, OWASP-LLM-2026, SOX, NIST-800-171, CMMC, CJIS-6.1.pdf, IRS-1075, SECTION-508, HHS-PART2, ONC-HTI1, FDA-AI-MD, FRB-MRM-2026, NYDFS-500 (non-200), ECOA-REG-B (non-200), NAIC-AI (non-200), COPPA, NYC-LL144, IL-AIVIA, UK-DP-AI, BR-LGPD (HTML wrapper), AU-PRIVACY-AI, SG-MODEL-AI (WAF), DOJ-DSP, EAR — plus 22 secondary documents.

**Out (8):** ISO-42001, ISO-42005, ISO-23894, ISO-38507, ISO-5338, ISO-24028, SOC2, PCI-DSS (paywalled).

---

## PDF inventory

- **Direct PDFs:** NIST-CSF2, OMB-M25-21/22, CJIS-6.1 (`/view` → true PDF).
- **True PDFs on disk (25 of 57 raw files):** the direct ones plus secondary `_pdfN` documents. `BR-LGPD.pdf` is an HTML wrapper (the true PDF was not landed).

---

## Troubleshooting

- **`HHS` / `business.defense.gov` 403:** the fix is a `mirrors` entry — `HHS-PART2` (42 CFR 2), `HIPAA` (45 CFR 164), and `CMMC` (32 CFR 170) now fall back to the codified eCFR text.
- **`eur-lex` JS shell:** the canonical URL returns a JavaScript shell; `mirrors` now carry the text (legislation.gov.uk for GDPR, the Consilium document server for the EU AI Act).
- **`BR-LGPD` HTML wrapper:** the PDF link is JS-generated, not an `<a href$=.pdf>`, and the only static source is Portuguese (which breaks the English-only corpus) — still open.
- **`CJIS-6.1` viewer URL:** `/view` serves an HTML viewer; the spider re-requests without `/view` to get the true PDF.
- **`verify_bronze` header/raw off by one:** `CJIS-6.1.html` and `CJIS-6.1.pdf` share a stem, so the check allows `abs(raw − headers) <= 1`.
- **A framework yields 0 chunks:** check `manifest.jsonl` for its `status` (`error` = non-200/WAF, `ok` but 0 chunks = served a shell or filtered at extraction). Prefer adding an authoritative `mirrors` entry in `sources.json` (an alternate surface that serves the text) over mutating Bronze or adding extraction filters.

---

## Related

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — design, data flow, decisions, extension points
- [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md) — every artifact and field
- [`FAQ.md`](FAQ.md#why-are-some-frameworks-empty) — why the gaps exist
