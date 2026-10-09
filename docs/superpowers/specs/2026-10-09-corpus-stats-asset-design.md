# Corpus statistics asset — design

- **Date:** 2026-10-09
- **Status:** Approved (design) — ready for an implementation plan
- **Author:** design session (with CommandCodeBot)

## Problem

The numbers in this repo's prose drift. The 2026-10-09 data refresh changed the corpus
(2,041 chunks, 5 gaps) and the only things that followed were the **auto-synced block
regions** — every hand-written number went stale: README's "honest gaps" table, the HF
card's gap prose, and the inline counts scattered through `DATA_DICTIONARY`,
`DATA_PIPELINE`, `COOKBOOK`, `ARCHITECTURE`, and the compliance-officer references. A
manual pass fixed them, which is a process that will fail again next run.

The root cause is that the volatile statistics have **no single source of truth** — they
are recomputed in a Python function and then restated by hand in a dozen places.

## Goal

Make the corpus statistics a **first-class data asset** that is the single source of truth
for every volatile number, and drive both the published docs and the shipped artifact from
it, so drift becomes structurally impossible.

### Non-goals

- Not a general template engine; rendering stays code, not a config language.
- Not converting structural constants (`512`, `50`, "min 50 words", hash lengths) — those
  are stable prose, not statistics.
- Not generating entire documents; surrounding prose stays hand-written.

## Approved decisions

1. **Scope:** the asset is *both* an internal source of truth **and** a published artifact
   (release + Hugging Face).
2. **Shape:** a small family of **wide CSVs**, not one file.
3. **Coverage:** **hybrid** — generated block regions carry the bulk; a curated set of
   inline markers covers numbers that must sit inside a sentence.
4. **Ownership:** produced by a **pipeline stage** (`build-stats`), not a docs script.
5. **Architecture:** **Approach 1 — named renderers over a CSV-backed value map.**
6. **Shipping:** one `corpus-stats-<run_id>.zip` **plus** the plain `corpus_stats.csv`.
7. **Internal docs:** the conversion rule also applies to the skill references and the
   ROADMAP (counts become markers; the watchlist's per-framework prose stays hand-written).

## The statistics asset (`data/stats/`)

Produced by `scripts/build_stats.py` from `data/sources.json` + `data/bronze/<run>/manifest.jsonl`
+ `data/silver/compliance_chunks.parquet` — the same inputs `sync_published.compute_stats()`
reads today. Committed.

| File | Columns |
|---|---|
| `corpus_stats.csv` | one row of scalars: `run_id, chunks, docs, frameworks_present, frameworks_total, tokens, chunk_pdf, chunk_html, median_words, raw_files, raw_pdf, raw_html, raw_mib, manifest_ok, manifest_skipped, manifest_error, sources_total, sources_public, sources_skipped, top3_share` |
| `gaps.csv` | `id, cause` (cause derived from manifest status: non-200 vs shell/wrapper) |
| `domains.csv` | `domain, chunks` |
| `top_documents.csv` | `framework_id, chunks` |
| `paywalled.csv` | `id` |

Values are **canonical and unformatted** (`chunks=2041`, `top3_share=0.449`). Presentation
is the renderer's job. Derived values (`top3_share`) are computed by the generator.

**Pipeline placement:** a new `pixi run build-stats` task, run after `build-silver` in
`pipeline` and in the monthly release; committed, attached to the GitHub Release, and
uploaded with the HF dataset.

## The value map and renderers (`scripts/corpus_stats.py`)

Two modules, one concern each:

- **`scripts/build_stats.py`** — the writer. Pipeline stage only.
- **`scripts/corpus_stats.py`** — the reader/presenter. `import`-able, stdlib-only (`csv`),
  no third-party deps.

`corpus_stats.py` exposes:

- `load()` → the raw CSV rows (machine view).
- `values()` → `dict[str, str]`, scalar key → formatted string (`"chunks" -> "2,041"`,
  `"top3_share" -> "~45%"`).
- Named renderers returning Markdown without a trailing newline (same contract as today's
  `render_*`): `headline()`, `stats_bullets()`, `gaps_table()`, `domains_table()`,
  `top_documents()`.

Formatting lives in one `FORMATS` table keyed by column name, with sane defaults (ints →
thousands-separated; `raw_mib` → `"46 MB"`; `tokens` → `"~1,029,983"`; known percent keys →
`"~45%"`). This module is the single place that knows the CSV filenames and column names.

## Markers and the doc renderer

One marker syntax for both blocks and inline values:

```
<!-- sync:NAME -->…last rendered content…<!-- /sync:NAME -->
```

Resolution by `NAME`:

- a **renderer name** → the inner block is replaced by that renderer's output;
- a **scalar key** → the inner text must equal `values()[NAME]`;
- an **unknown name** → **hard fail** (fail-closed).

The per-file region allowlist is dropped — any file may host any marker, and the
unknown-name failure replaces the "missing marker" check. Rendering lives in
`sync_published.py`, which gains the scalar path and reads `corpus_stats`. `--check`
compares committed content against a fresh render and exits 1 on any difference.

## Enforcement (CI)

1. **`check-stats`** — run `build-stats`, then `git diff --exit-code data/stats/`.
2. **`verify-stats`** — assert the CSVs agree with the source of truth: `chunks` == parquet
   rows, `frameworks_present` == distinct stems, manifest counts match, every `gaps.csv` id
   has 0 chunks.
3. **`check-docs`** — re-render every block + inline marker; unknown marker names fail.

## Shipping

- Release: `corpus-stats-<run_id>.zip` (all five) plus a loose `corpus_stats.csv`.
- Hugging Face: uploaded by `publish_hf.py`, with a one-line mention on the card.

## Conversion rule

Any number that **changes between runs** becomes a marker; structural constants stay prose.
Applied to README, the HF card, FAQ, `DATA_DICTIONARY`, `DATA_PIPELINE`, `COOKBOOK`,
`ARCHITECTURE`, the compliance-officer references, and the ROADMAP progress note.

## Testing

A minimal stdlib suite (no new dependency), `tests/test_corpus_stats.py`, via a
`pixi run test` task and CI:

- `values()` formatting per key.
- `gaps_table` groups by cause and orders deterministically.
- `build_stats` determinism (run twice → byte-identical).
- Contract: a bogus marker name → `check-docs` exits 1; a hand-edited value → exits 1, and
  `sync` repairs it.

## Rollout (small PRs)

1. `build_stats` + `corpus_stats` + tests.
2. Convert README / HF card / FAQ.
3. Convert `DATA_*` / COOKBOOK / ARCHITECTURE.
4. Convert the skill references + ROADMAP.
5. CI gates + release/HF shipping.

## Edge cases

- **Markers inside fenced code blocks don't render cleanly** (the HTML comment shows
  literally). Resolution: do **not** mark code-fence values — drop hard-coded
  "sample output" lines (the surrounding code already computes them) or move the number
  into adjacent prose. A code-fence marker form is a last resort, not planned.
- Unreadable/missing CSV → hard error; a renderer asking for a missing column → raises.

## Open questions

None — all design forks resolved above.
