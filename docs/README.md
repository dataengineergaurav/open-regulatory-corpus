# Documentation

This is the map. The [project README](../README.md) is the front door; everything below is the depth behind it. Pick the path that matches what you're trying to do.

## Where do I start?

| I want to… | Read |
|---|---|
| Understand what this project is and use the data today | [Project README](../README.md) |
| Know **why** it's built this way and how the parts connect | [ARCHITECTURE.md](ARCHITECTURE.md) |
| **Run** the pipeline, or debug a crawl that failed | [DATA_PIPELINE.md](DATA_PIPELINE.md) |
| Look up **exactly** what a field or file contains | [DATA_DICTIONARY.md](DATA_DICTIONARY.md) |
| Do a **task** — filter, search, compare, export for RAG | [COOKBOOK.md](COOKBOOK.md) |
| Get answers about gaps, licensing, provenance, roadmap | [FAQ.md](FAQ.md) |
| See the prioritized engineering roadmap (issues, Now / Next / Later) | [ROADMAP.md](ROADMAP.md) |
| Run code without installing anything | [notebooks/](../notebooks/) |

## The docs, in one screen

```
README.md              The front door: what, why, quickstart, by-the-numbers.
docs/
├── README.md          ← you are here — the index.
├── ARCHITECTURE.md    System design: medallion model, component roles,
│                      data flow, design decisions, how to extend.
├── DATA_PIPELINE.md   Operational runbook: stages, commands, source
│                      inventory, PDF inventory, troubleshooting.
├── DATA_DICTIONARY.md Field-level reference for every artifact.
├── COOKBOOK.md        Task-oriented recipes with copy-paste code.
├── FAQ.md             Questions, honest gaps, licensing, roadmap.
└── ROADMAP.md         Prioritized engineering roadmap (issues, Now / Next / Later).
```

## The mental model in 60 seconds

1. **`data/sources.json` is the single source of truth.** One JSON array of sources drives the entire crawl. Nothing else hard-codes a URL.
2. **Bronze is sacred.** Raw bytes land first, unmodified, named by magic bytes, with a manifest that records `ok` / `skipped` / `error` for every source.
3. **Silver is derived, and disposable.** It is rebuilt from Bronze on demand. It can always be regenerated; Bronze cannot be re-fetched identically (the web changes), which is why Bronze is the durable artifact.
4. **Provenance is not optional.** Every chunk knows its `framework_id`, its `source` file, and the `sha256` of the document it came from.
5. **Gaps are data.** A framework with zero chunks is recorded and explained, not quietly dropped.

## Conventions used in these docs

- **Bronze / Silver** — medallion stages. Bronze = raw landing; Silver = cleaned + chunked. A "Gold" stage (embeddings) is planned but not built.
- **`framework_id`** — a stable short code (e.g. `NIST-CSF2`). A `_pdfN` suffix (`SOX_pdf1`) marks a *secondary* document belonging to the same framework.
- **`run_id`** — the identifier of one pipeline execution, e.g. `2026-09-01_1903` (date + HHMM).
- **`*` marker** — in tables, denotes a framework tracked but currently producing 0 chunks.
- **42** — not the answer. It's the number of characters in a zero-width space. Never trust a doc that cites it.

## Keeping these docs honest

These documents are part of the product, not an afterthought. When the pipeline changes, the doc that describes it changes in the same PR. If you find a number here that doesn't match the artifacts, that's a bug — see [`docs/FAQ.md`](FAQ.md) for how to report it.
