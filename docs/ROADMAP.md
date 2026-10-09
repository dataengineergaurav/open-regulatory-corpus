# Roadmap — Prioritized Issue List

The engineering roadmap for the Open Regulatory Corpus, as a prioritized issue list. Every item is
live as a GitHub issue on
[`dataengineergaurav/open-regulatory-corpus`](https://github.com/dataengineergaurav/open-regulatory-corpus/issues)
(the number in each heading is that issue); this file is the source of record.

Priorities reflect one thesis: **the corpus's credibility is its coverage and its change signal,
not its chunk count.** P0 unblocks credibility; P1 makes change visible and coverage honest; P2 is
data quality and developer experience.

**Labels used:** `roadmap`, `p0`/`p1`/`p2`, and one area label (`gap-recovery`, `source`,
`pipeline`, `data-quality`, `publishing`, `dx`).

The Now / Next / Later grouping maps cleanly onto a GitHub Project board if you ever want one — the
issue bodies are already written for it. No board is required to use this list.

**Progress (run `2026-10-09`):** R1–R4 and R6–R14 shipped (#15–#25). R5 is partial — `HIPAA`,
`HHS-PART2`, `CMMC`, `IL-AIVIA` recovered via `mirrors`, while `BR-LGPD` remains open and
`NYDFS-500` / `ECOA-REG-B` / `NAIC-AI` / `SG-MODEL-AI` regressed on the last run. R12 (repo
identity) is blocked on an account-level decision.

---

## Now (P0) — Unblock credibility

### R1 — Recover GDPR from a fetchable authoritative source (#1)

- **Priority:** P0 · **Area:** sources · **Labels:** `gap-recovery`, `source`, `p0`
- **Problem:** `GDPR` is `public: true` but yields **0 chunks** — EUR-Lex serves a ~2 KB JavaScript
  shell. The corpus cannot credibly claim privacy coverage without GDPR.
- **Proposal:** Point `sources.json` at a register view that serves text (CELEX `32016R0679`), or add
  it as a mirror (R3). Verify by fetching — the bytes must be the regulation, not a shell.
- **Definition of done:** `manifest` shows `ok` **and** Silver yields >0 chunks for GDPR.
- **Depends on:** — · **Refs:** `docs/FAQ.md#why-are-some-frameworks-empty`

### R2 — Recover the EU AI Act from a fetchable authoritative source (#2)

- **Priority:** P0 · **Area:** sources · **Labels:** `gap-recovery`, `source`, `p0`
- **Problem:** `EU-AI-ACT` yields 0 chunks (EUR-Lex JS shell). This is the single most consequential
  AI-governance text; its absence undermines the whole AI Governance domain.
- **Proposal:** Same recovery as R1 using the consolidated register view (CELEX `32024R1689`).
- **Definition of done:** `ok` in the manifest **and** >0 chunks in Silver.
- **Depends on:** — (can share the mirror mechanism from R3)

### R3 — Add a mirror registry to `sources.json` and teach the spider to fall back (#3)

- **Priority:** P0 · **Area:** pipeline · **Labels:** `pipeline`, `source`, `p0`
- **Problem:** Recovery today is a **code change** (special cases in `generic.py`). WAF/JS blocks
  recur, so recovery must be a **config change**.
- **Proposal:** Extend the schema to `{"id","url","public","mirrors":[…]}`; the spider tries `url`
  then each mirror, recording which one won in the manifest. Document in `DATA_DICTIONARY.md` and
  have the compliance-officer watchlist read `mirrors`.
- **Definition of done:** schema documented; spider falls back through mirrors; `verify_bronze`
  unchanged; at least one gap recovered via a mirror (R1/R2).
- **Depends on:** —

### R4 — Derive `verify_bronze` invariants from `sources.json` (#4)

- **Priority:** P0 · **Area:** pipeline · **Labels:** `pipeline`, `p0`
- **Problem:** the verifier hard-codes "exactly 8 skipped / ≥34 ok". Adding a framework fails CI with
  a confusing message — friction against the project's own "add a framework = one JSON object" claim.
- **Proposal:** compute `expected_skipped = count(public == false)` and a derived `ok` floor instead
  of magic numbers.
- **Definition of done:** adding a public or paywalled framework needs **no** verifier edit; CI green.
- **Depends on:** —

---

## Next (P1) — Make change visible and coverage honest

### R5 — Recover the remaining five gaps (#5, epic)

- **Priority:** P1 · **Area:** sources · **Labels:** `gap-recovery`, `source`, `p1`
- **Problem:** `HIPAA`, `HHS-PART2`, `CMMC`, `IL-AIVIA`, `BR-LGPD` each yield 0 chunks.
- **Proposal:** one sub-issue per framework, each using the R3 mirror mechanism:
  `HIPAA` / `HHS-PART2` (HHS WAF 403 → alternate HHS surface or eCFR 45 CFR 160/164, 42 CFR Part 2);
  `CMMC` (DoD 403 → DoD CIO / Federal Register program rule); `IL-AIVIA` (timeout → ILGA public-act
  page); `BR-LGPD` (HTML wrapper → direct `gov.br`/planalto PDF).
- **Definition of done (per sub-issue):** `ok` + >0 chunks; gap-list shrinks by one.
- **Depends on:** R3

### R6 — Drift detection: diff `sha256_raw` across runs (#6)

- **Priority:** P1 · **Area:** pipeline · **Labels:** `pipeline`, `p1`
- **Problem:** documents re-ingest silently; a changed document with no version bump is invisible.
- **Proposal:** a read-only script that compares the current `manifest.jsonl` against the previous
  run's and reports added / changed / removed documents by hash. No network — it compares manifests.
- **Definition of done:** deterministic changed-document report; wired into the monthly workflow.
- **Depends on:** — · **Refs:** roadmap item #4 in `docs/FAQ.md`

### R7 — Publish a regulatory changelog (derived artifact + feed) (#7)

- **Priority:** P1 · **Area:** publishing · **Labels:** `publishing`, `p1`
- **Problem:** the corpus is a snapshot; practitioners actually want the **change signal**
  ("NIST 800-53 r5 upd2 → upd3", "EU AI Act GPAI obligations in force").
- **Proposal:** render R6's diff into a human-readable per-release changelog, optionally an RSS/JSON
  feed. This is the project's strongest differentiator.
- **Definition of done:** a `changelog` artifact ships each release and is linked from the README.
- **Depends on:** R6

### R8 — Publish a balanced per-framework slice (or weights) (#8)

- **Priority:** P1 · **Area:** data-quality · **Labels:** `data-quality`, `p1`
- **Problem:** `CJIS-6.1` + `IRS-1075` + `SOX` ≈ **45%** of chunks (`CJIS-6.1` alone ≈ 23%). Naive
  consumers get a criminal-justice-security corpus with a compliance garnish.
- **Proposal:** materialize cookbook recipe 8 as a shipped, capped/weighted companion slice — or add
  a documented per-framework weight column so consumers don't rediscover the skew.
- **Definition of done:** a documented balanced artifact exists and is referenced from `COOKBOOK.md`.
- **Depends on:** —

---

## Later (P2) — Data quality and developer experience

### R9 — Extraction-confidence flags for PDFs (#9)

- **Priority:** P2 · **Area:** data-quality · **Labels:** `data-quality`, `p2`
- **Problem:** provenance proves *where* text came from, not that it was read correctly; regulatory
  tables (control mappings, thresholds, penalties) are exactly where PyMuPDF flattens into
  misleading prose.
- **Proposal:** flag table-heavy / suspiciously short / garbled pages in a `confidence` signal or a
  side report, rather than silently shipping them.
- **Definition of done:** the signal exists and is documented in `DATA_DICTIONARY.md`.

### R10 — Redefine Gold as deterministic artifacts (#10)

- **Priority:** P2 · **Area:** pipeline · **Labels:** `pipeline`, `p2`
- **Problem:** the planned Gold stage (embeddings) pins the project to a model version and breaks
  Silver's "rebuildable, no-GPU" promise.
- **Proposal:** Gold = model-free, deterministic artifacts (topic/control crosswalks, exact token
  counts, framework index). Keep embeddings a **documented consumer recipe**, not a committed stage.
- **Definition of done:** design documented; any `build_gold.py` never mutates Silver.

### R11 — `sources.schema.json` + PR validation (#11)

- **Priority:** P2 · **Area:** dx · **Labels:** `dx`, `p2`
- **Problem:** "add one JSON object" is a friendly promise, not an enforced contract.
- **Proposal:** a JSON Schema for `sources.json`, plus a PR check that fetches each URL and reports
  content-type/size and lints `id` uniqueness/format.
- **Definition of done:** CI validates `sources.json` on every PR.

### R12 — Unify repository identity (GitHub vs Hugging Face) (#12)

- **Priority:** P2 · **Area:** dx · **Labels:** `dx`, `p2`
- **Problem:** GitHub `dataengineergaurav` vs Hugging Face `GauravGurjar` — a governance smell for a
  project whose thesis is provenance.
- **Proposal:** pick one handle everywhere (repo, dataset card, `sync_published.py` defaults, docs).
- **Definition of done:** a single identity across all surfaces.

### R13 — Clause/control-aware chunking (#13)

- **Priority:** P2 · **Area:** data-quality · **Labels:** `data-quality`, `p2`
- **Problem:** fixed 512-token windows cut across control boundaries; regulatory reasoning happens
  at the control/clause level (e.g. `AC-2`, §164.312).
- **Proposal:** opt-in section-aware chunking that respects numbered headings, with the fixed-window
  chunker as fallback.
- **Definition of done:** the chunker emits section-aware boundaries where numbering exists;
  documented; default behavior unchanged.

### R14 — Schedule the gap-recovery watcher (#14)

- **Priority:** P2 · **Area:** dx · **Labels:** `dx`, `pipeline`, `p2`
- **Problem:** the open gaps should be re-probed automatically so recovery is noticed, not missed.
- **Proposal:** wire the compliance-officer `gap-recovery` variant into a **durable weekly GitHub
  Action** (not a 7-day-expiring agent cron) that probes only the open gaps and opens an issue/PR
  when one starts serving text.
- **Definition of done:** the workflow exists and is a no-op when nothing changed.
- **Depends on:** R3, R5

---

## Milestones (suggested)

| Milestone | Issues | Theme |
|---|---|---|
| **M1 — Credibility** | R1, R2, R3, R4 | Close the flagship gaps and make recovery repeatable |
| **M2 — Change signal** | R6, R7 | Turn the corpus into a changelog |
| **M3 — Coverage & honesty** | R5, R8 | Finish the gap list; ship a balanced slice |
| **M4 — Quality & DX** | R9–R14 | Extraction fidelity, schema enforcement, automation |

---

## Adding an issue

```bash
gh issue create --repo dataengineergaurav/open-regulatory-corpus \
  --title "R15 — <title>" --label roadmap,p2,<area> --body-file -
```

## Keeping this honest

This file is the roadmap of record. When an issue ships, close it on GitHub and update the milestone
roll-up here in the same PR — the same rule the rest of `docs/` follows.
