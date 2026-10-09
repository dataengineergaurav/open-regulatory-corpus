# Data Dictionary

Every artifact this project produces, and every field inside it. If you only read one reference page, make it this one.

All examples are taken verbatim from the current run (`2026-09-01_1903`).

---

## Artifact map

```
data/
├── sources.json                          the curated input (46 entries)
├── bronze/
│   ├── latest -> 2026-09-01_1903         symlink to newest run
│   └── 2026-09-01_1903/
│       ├── manifest.jsonl                70 lines: what happened to each source
│       ├── scrapy_stats.json             crawl telemetry
│       ├── raw/<ID>.<ext>                58 verbatim files (Release asset)
│       └── headers/<ID>.json             58 HTTP response records (Release asset)
└── silver/
    ├── compliance_chunks.parquet         1,519 rows × 7 cols (the usable data)
    ├── balanced_slice.parquet            capped companion slice (≤30 chunks/framework)
    ├── quality_report.json               per-document extraction-quality flags
    └── silver_stats.json                 one-line summary
```

> `raw/` and `headers/` are `.gitignore`d — they are ~43 MB per run and live as GitHub Release assets. The parquet, manifest, and stats stay in git.

---

## `data/sources.json`

The single source of truth. A flat JSON array; the only hand-edited file.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | ✅ | Stable framework code. Upstream key for `framework_id` in Silver. Must be unique. |
| `url` | string | ✅ | The URL to fetch (the canonical source). |
| `public` | boolean | ✅ | `true` = fetch it. `false` = paywalled/gated; record as skipped, **never request**. |
| `mirrors` | string[] | ⬜ | Authoritative alternate URLs, tried in order when `url` yields nothing usable. Optional. |

```json
{"id": "NIST-CSF2", "url": "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf", "public": true}
{"id": "ISO-42001", "url": "https://www.iso.org/standard/42001", "public": false}
{"id": "GDPR", "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng", "public": true,
 "mirrors": ["https://www.legislation.gov.uk/eur/2016/679/data.xht"]}
```

`mirrors` is the recovery mechanism for sources whose canonical URL is blocked or served as a
JavaScript shell. The spider tries `url` first; if the response is empty, a shell, or a WAF
challenge — or the request fails — it falls back through `mirrors` in order and records whichever
URL produced the document. A mirror is an authoritative alternate for the **same framework** (a
register view, an institutional document server, or the codified text, e.g. eCFR for a
CFR-implemented rule); never an unofficial copy.

Current contents: **46 entries = 38 public + 8 paywalled; 5 carry `mirrors`.**

Validated by `scripts/validate_sources.py` against [`data/sources.schema.json`](../data/sources.schema.json) — required fields, types, `id` format/uniqueness, URL shape, and no unknown keys. CI runs it on every PR, so a malformed registry fails before a crawl.

---

## Framework ID conventions

`framework_id` is a string with two rules worth knowing:

- **Stem** — the base code from `sources.json` (`SOX`, `CJIS-6.1`).
- **`_pdfN` suffix** — a *secondary* document discovered by following PDF links on the landing page (`SOX_pdf1`, `SOX_pdf2`, `NIST-800-171_pdf2`).

This matters for filtering: `df.framework_id == "SOX"` gets only the primary document, while `df.framework_id.str.startswith("SOX")` gets all three. To roll up to a framework, split on the suffix:

```python
df["stem"] = df.framework_id.str.split("_pdf").str[0]
```

**Present in Silver:** 31 stems across 54 `framework_id` values.

---

## `data/bronze/<run_id>/manifest.jsonl`

One JSON object per line. It is **append-ordered but not strictly chronological** — the 8 `skipped` rows are written first (at pipeline start, before any request), then `ok` and `error` rows as the crawl proceeds.

There are exactly **three line shapes**, distinguished by `status`:

### Shape 1 — `ok` (58 lines)

```json
{"id": "NIST-CSF2", "url": "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
 "status": "ok", "content_type": "application/pdf", "bytes": 1518858,
 "sha256_raw": "3c31f46fee98cac0c4323453e5109291a213b4de7fef8c058af9bf67f717433c",
 "fetched_at": "2026-09-01T13:34:01Z"}
```

| Field | Meaning |
|---|---|
| `bytes` | Size of the raw response body |
| `sha256_raw` | Hash of the **raw bytes** (before any cleaning) |
| `content_type` | HTTP `Content-Type` header |
| `fetched_at` | UTC timestamp |

### Shape 2 — `skipped_public_only` (8 lines)

```json
{"id": "ISO-42001", "url": "https://www.iso.org/standard/42001",
 "status": "skipped_public_only", "reason": "paywalled/gated, public-only mode"}
```

No `request` was ever sent. This is the ethical record of a deliberate omission.

### Shape 3 — `error` (4 lines)

```json
{"id": "HIPAA", "url": "https://www.hhs.gov/hipaa/...",
 "status": "error", "error": "Ignoring non-200 response", "fetched_at": "2026-09-01T13:34:01Z"}
```

| Field | Meaning |
|---|---|
| `error` | The failure reason as reported by Scrapy (e.g. `Ignoring non-200 response`, `User timeout caused connection failure.`) |

### Line counts

| Status | Count | Interpretation |
|---|---|---|
| `ok` | 58 | Landed raw bytes |
| `skipped_public_only` | 8 | Deliberately not fetched |
| `error` | 4 | Attempted and failed (WAF 403 / timeout) |
| **Total** | **70** | |

> `ok` (58) matches the 58 files in `raw/`. Headers may total 58 too; the one historical collision is `CJIS-6.1`, which lands as both `.html` and `.pdf` from a shared stem.

---

## `data/bronze/<run_id>/raw/`

58 files, named `<ID><ext>`. The extension is chosen by **magic bytes first**, then content type, then URL — in that order — so the extension always reflects the true format:

- starts with `%PDF` → `.pdf`
- `Content-Type` contains `pdf` → `.pdf`
- URL ends `.pdf` but body is HTML → `.html` (a wrapper page, not a lie)
- otherwise → `.html`

Files are verbatim bytes. **Bronze is never mutated.**

---

## `data/bronze/<run_id>/headers/<ID>.json`

The full HTTP response record, one file per fetched source. Written by `RawPipeline`.

| Field | Type | Meaning |
|---|---|---|
| `id` | string | Framework code |
| `url` | string | The URL requested (the original, not the final) |
| `final_url` | string | URL after redirects |
| `status` | int | HTTP status code |
| `content_type` | string | Response content type |
| `headers` | object | All response headers, keys lower-cased |
| `fetched_at` | string | UTC timestamp |
| `bytes` | int | Body length |

---

## `data/bronze/<run_id>/scrapy_stats.json`

Raw Scrapy telemetry for the run. The fields most worth knowing:

| Key | Example | Meaning |
|---|---|---|
| `downloader/response_status_count/200` | `84` | Successful responses |
| `downloader/response_status_count/403` | `5` | Blocked (WAF) |
| `downloader/response_status_count/404` | `2` | Not found |
| `downloader/exception_count` | `6` | Network-level failures |
| `item_scraped_count` | `58` | Items emitted to the pipeline |
| `retry/count` | `4` | Requests retried |
| `robotstxt/response_count` | `33` | robots.txt files consulted |
| `httpcache/hit` / `miss` | `99` / `6` | Cache effectiveness |

The count is higher than 46 because the crawl follows robots.txt, PDF links, retries, and redirects.

---

## `data/silver/compliance_chunks.parquet`

The product. **1,519 rows × 7 columns**, ~1.6 MiB, Parquet via Apache Arrow. Every column is provenance-bearing.

| # | Column | Type | Null? | Example | Notes |
|---|---|---|---|---|---|
| 1 | `framework_id` | string | no | `SOX_pdf1` | Stem, or stem + `_pdfN` for secondary docs |
| 2 | `chunk_id` | string | no | `SOX_pdf1-155` | `{framework_id}-{index}`, unique across the corpus |
| 3 | `text` | string | no | `"17% of issuers report interest rate risk…"` | The payload |
| 4 | `source` | string | no | `data/bronze/latest/raw/SOX_pdf1.pdf` | Path back to Bronze |
| 5 | `kind` | string | no | `pdf` / `html` | Which extractor produced it |
| 6 | `token_est` | float | no | `510.72` | `len(text.split()) * 1.33` |
| 7 | `sha256` | string | no | `4ebc14c5459f…` | Hash of the **extracted document text**; all chunks of a doc share it |

**Distribution (current run):** `kind` = 1,236 pdf / 283 html. 54 unique `sha256` (documents). 54 unique `framework_id`. 31 unique stems.

**Chunk sizing:** 512-token window with 50-token overlap, approximated as 384 words with 38-word overlap, minimum 50 words per chunk. Median chunk = 384 words ≈ 510.7 estimated tokens.

> **Note on `token_est`.** It is an *estimate* by design (`words × 1.33`), which is what lets the whole Silver stage — and the Colab notebooks — run without a tokenizer dependency. For exact counts, re-tokenize `text` yourself (e.g. `tiktoken`) in a Gold stage.

> **Note on `sha256`.** This is the hash of the *extracted text*, not the raw file (that's `sha256_raw` in the manifest). It is the dedup key: identical extracted text from two different URLs collapses to one document.

---

## `data/silver/silver_stats.json`

```json
{
  "run_id": "data/bronze/latest",
  "chunks": 1519,
  "docs": 54
}
```

`run_id` records the path the build read from (here, via the `latest` symlink). `docs` is the count of unique extracted documents (equal to unique `sha256`).

---

## `data/silver/balanced_slice.parquet`

A capped companion to `compliance_chunks.parquet` with the **same 7-column schema**. No
framework contributes more than 30 chunks (seed 0), which pulls the three largest
frameworks (`CJIS-6.1`, `IRS-1075`, `SOX` — most of the full corpus) down to about a fifth
of it. Built deterministically by `scripts/build_balanced_slice.py`; the full corpus is
left untouched. Use it whenever a blended metric must not be an implicit metric over CJIS.

`data/silver/balanced_slice.json` records the cap, seed, and resulting counts.

---

## `data/silver/quality_report.json`

Per-document extraction-quality flags, written by `build_silver.py`. Flags **annotate**;
nothing is dropped for them (dedup/short/WAF filtering happens before this).

```json
{"run_id": "…", "section_aware": false, "docs": 54, "flagged": 12,
 "entries": [{"framework_id": "CJIS-6.1", "kind": "pdf", "sha256": "…",
              "chars": 812345, "chunks": 466, "flags": ["table_heavy"]}]}
```

| Flag | Meaning |
|---|---|
| `short` | extracted text < 500 chars |
| `table_heavy` | > 25% of lines look tabular (2+ internal spaces) — a PDF table flattened by text extraction |
| `fragmented` | > 40% of lines are < 3 chars |
| `low_alpha` | < 55% of characters are letters (number/symbol soup) |
| `garbled` | replacement chars (`�`) or many `(cid:` glyphs |

`flagged` is the count of documents with at least one flag. Provenance is unchanged — the
`sha256` here is the same document hash used to group chunks.

---

## Provenance chain

Every chunk can be traced, end to end:

```
compliance_chunks.parquet row
  └─ source:  data/bronze/latest/raw/SOX_pdf1.pdf
       └─ (resolve latest symlink) data/bronze/2026-09-01_1903/raw/SOX_pdf1.pdf
            └─ manifest.jsonl row  → id: SOX_pdf1, sha256_raw, bytes, fetched_at
                 └─ url: https://www.sec.gov/news/studies/soxoffbalancerpt.pdf
                      └─ sources.json  → {"id": "SOX", ...}
```

To go from a chunk to its authoritative URL: `chunk.source` → filename stem → match `manifest.jsonl.id` → `manifest.url` → confirm in `sources.json`.

---

## Data quality guarantees

These hold for every release and are enforced (or measured) in code:

- ✅ Every chunk has a non-null `framework_id`, `chunk_id`, `text`, `source`, `kind`, `token_est`, `sha256`.
- ✅ `chunk_id` is unique across the corpus.
- ✅ `sha256` groups chunks by source document (no duplicate documents).
- ✅ Every `source` path resolves to a file that existed at build time.
- ⚠️ `token_est` is an approximation, not a tokenizer count.
- ⚠️ 7 of 38 public frameworks currently yield 0 chunks (documented in [`FAQ.md`](FAQ.md)).
