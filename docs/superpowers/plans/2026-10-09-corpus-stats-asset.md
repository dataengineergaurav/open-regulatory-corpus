# Corpus Statistics Asset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the corpus statistics a first-class data asset (`data/stats/*.csv`, produced by a pipeline stage) that is the single source of truth for every volatile number, and drive all published and internal docs from it via unified `<!-- sync:NAME -->` markers.

**Architecture:** `build_stats.py` writes five wide CSVs from `sources.json` + the manifest + the parquet. `corpus_stats.py` (stdlib-only) reads them and exposes a scalar `values()` map plus named Markdown renderers. `sync_published.py` resolves every marker by name — renderer or scalar key — and fails closed on an unknown name. Three CI gates (`check-stats`, `verify-stats`, `check-docs`) keep the CSVs, the docs, and the artifacts mutually consistent.

**Tech Stack:** Python 3.12, `csv`/`json`/`re` (stdlib), `pyarrow`/`pandas` (already deps), Scrapy/pixi for the pipeline. Tests use stdlib `unittest` (no new dependency).

**Spec:** `docs/superpowers/specs/2026-10-09-corpus-stats-asset-design.md`

## Global Constraints

- `corpus_stats.py` is **stdlib-only** — `csv`, `json`, `re`, `pathlib`, `collections`. No third-party imports.
- CSV values are **canonical and unformatted**: `chunks=2041` (int), `top3_share=0.449` (float), ids verbatim.
- Presentation examples that tests must pin: `chunks → "2,041"`, `tokens → "~1,029,983"`, `raw_mib → "46 MB"`, `top3_share → "~45%"`, `chunk_pdf → "1,292"`.
- **Structural constants stay prose** (`512`, `50`, "min 50 words", hash lengths, thresholds) — never marked.
- **Unknown marker name is a hard failure** (`check-docs` exits non-zero); names never silently skip.
- **No markers inside fenced code blocks** — such numbers are dropped or moved to prose.
- CSV family is exactly five files: `corpus_stats.csv`, `gaps.csv`, `domains.csv`, `top_documents.csv`, `paywalled.csv`.
- Tests run with `python -m unittest discover -s tests -v`; a `pixi run test` task wraps it.

## File Structure

- `scripts/build_stats.py` — **create.** Writer: artifacts → `data/stats/*.csv`. One job.
- `scripts/corpus_stats.py` — **create.** Reader/presenter: `load()`, `values()`, `RENDERERS`. One job.
- `scripts/verify_stats.py` — **create.** Asserts the CSVs agree with the artifacts.
- `scripts/sync_published.py` — **modify.** Replace the block-region renderer with the unified marker engine.
- `tests/test_corpus_stats.py`, `tests/test_sync_markers.py` — **create.** stdlib `unittest`.
- `data/stats/*.csv` — **generated, committed.**
- Docs — **modify** (README, `HF_DATASET_CARD.md`, `docs/*`, skill references).
- `pixi.toml`, `.github/workflows/{ci,monthly-release}.yml` — **modify** (tasks, gates, shipping).

## Review Focus

Inputs/conditions the spec implies but which no task's happy-path test exercises; each gets a test in its owning task:

1. A marker whose name is unknown (typo) — must fail closed, not render untouched.
2. A block marker spanning multiple lines vs an inline one on a single line — both must resolve.
3. A CSV file absent or unreadable — must raise, never silently yield empty values.
4. All frameworks present (empty `gaps.csv`) — the gaps renderer must still produce a valid statement + table.
5. A `cause` string containing a comma — must round-trip through the CSV quoted.

---

### Task 1: `build_stats.py` — generate the CSV family

**Files:**
- Create: `scripts/build_stats.py`
- Test: `tests/test_corpus_stats.py`

**Interfaces:**
- Produces: `STATS_DIR: Path`, `COLUMNS: dict[str, list[str]]`, `collect() -> dict[str, list[dict]]`, `write(stats_dir: Path) -> None`, `main() -> int`.

- [ ] **Step 1: Write the failing test**

```python
import sys, csv, tempfile, pathlib
sys.path.insert(0, "scripts")
import build_stats as bs

def test_collect_has_five_tables():
    data = bs.collect()
    assert set(data) == {"corpus_stats", "gaps", "domains", "top_documents", "paywalled"}

def test_collect_is_deterministic():
    assert bs.collect() == bs.collect()

def test_write_roundtrips_and_is_byte_stable():
    with tempfile.TemporaryDirectory() as d:
        bs.write(pathlib.Path(d)); first = {p.name: p.read_bytes() for p in pathlib.Path(d).glob("*.csv")}
        bs.write(pathlib.Path(d)); second = {p.name: p.read_bytes() for p in pathlib.Path(d).glob("*.csv")}
    assert first == second and set(first) == {f"{k}.csv" for k in bs.COLUMNS}

def test_corpus_stats_row_keys_match_columns():
    row = bs.collect()["corpus_stats"][0]
    assert list(row) == bs.COLUMNS["corpus_stats"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_corpus_stats -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'build_stats'`

- [ ] **Step 3: Implement `scripts/build_stats.py`**

Reuse the artifact-reading logic already in `sync_published.compute_stats()` (parquet rows/chunks, manifest counts, sources counts). Key points: `COLUMNS` declares the exact header order per file; `collect()` returns rows in that order; `write()` uses the `csv` module with `newline=""` and sorts `top_documents` by `chunks` desc then id, `gaps` by id, `domains` by the fixed five-domain order.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_corpus_stats -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Generate and commit the asset**

Run: `python scripts/build_stats.py && git add scripts/build_stats.py tests/test_corpus_stats.py data/stats/ && git commit -m "feat: generate the corpus statistics CSV family"`

---

### Task 2: `corpus_stats.py` — load, `values()`, and formatting

**Files:**
- Create: `scripts/corpus_stats.py`
- Test: `tests/test_corpus_stats.py` (append)

**Interfaces:**
- Consumes: `data/stats/*.csv` (Task 1).
- Produces: `load() -> dict[str, list[dict]]`, `FORMATS: dict[str, str]`, `values() -> dict[str, str]`.

- [ ] **Step 1: Write the failing test**

```python
import corpus_stats as cs

def test_values_pins_formats():
    v = cs.values()
    assert v["chunks"] == "2,041"
    assert v["tokens"] == "~1,029,983"
    assert v["raw_mib"] == "46 MB"
    assert v["top3_share"] == "~45%"
    assert v["chunk_pdf"] == "1,292"

def test_values_raises_on_missing_dir(monkeypatch=None):
    import pathlib, tempfile, importlib
    with tempfile.TemporaryDirectory() as d:
        saved = cs.DATA_DIR
        cs.DATA_DIR = pathlib.Path(d)
        try:
            try:
                cs.values(); assert False, "expected an error"
            except (FileNotFoundError, KeyError):
                pass
        finally:
            cs.DATA_DIR = saved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_corpus_stats -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'corpus_stats'`

- [ ] **Step 3: Implement `scripts/corpus_stats.py`**

`load()` reads every file in `DATA_DIR` via `csv.DictReader`; a missing directory raises `FileNotFoundError` (Review Focus 3). `FORMATS` maps scalar column names to a format kind (`int` default → thousands-separated; `mib` → `"46 MB"`; `tokens` → `"~…"`; `pct` → `"~45%"`; `str` → verbatim). `values()` returns `{column: format(cell)}` for the single `corpus_stats` row.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_corpus_stats -v`
Expected: PASS

- [ ] **Step 5: Commit**

Run: `git add scripts/corpus_stats.py tests/test_corpus_stats.py && git commit -m "feat: corpus_stats value map + formatting"`

---

### Task 3: `corpus_stats.py` — named renderers

**Files:**
- Modify: `scripts/corpus_stats.py`
- Test: `tests/test_corpus_stats.py` (append)

**Interfaces:**
- Consumes: `load()`, `values()` (Task 2).
- Produces: `headline() -> str`, `stats_bullets() -> str`, `gaps_table() -> str`, `domains_table() -> str`, `top_documents() -> str`, `RENDERERS: dict[str, Callable[[], str]]`.

- [ ] **Step 1: Write the failing test**

```python
import corpus_stats as cs

def test_renderers_registered_and_nonempty():
    assert set(cs.RENDERERS) == {"headline", "stats_bullets", "gaps_table", "domains_table", "top_documents"}
    for fn in cs.RENDERERS.values():
        assert fn().strip()

def test_gaps_table_groups_by_cause_and_orders_deterministically():
    t = cs.gaps_table()
    assert t.splitlines()[0].startswith("**5** of the 38")
    assert "| Framework | Why it's empty |" in t
    assert cs.gaps_table() == t

def test_gaps_table_handles_empty(monkeypatch=None):
    saved = cs.load
    cs.load = lambda: {"corpus_stats": saved()["corpus_stats"], "gaps": []}
    try:
        assert "0" in cs.gaps_table().splitlines()[0]
    finally:
        cs.load = saved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_corpus_stats -v`
Expected: FAIL — `AttributeError: module 'corpus_stats' has no attribute 'RENDERERS'`

- [ ] **Step 3: Implement the renderers**

`gaps_table()` groups rows by `cause` (sorted by `(cause, id)`), emits `**N** of the 38 public frameworks currently produce **zero chunks**:` then a 2-column table; with zero rows it emits `**0** of the 38 …` and an empty table (Review Focus 4). `stats_bullets()`, `domains_table()`, `top_documents()`, `headline()` reproduce the current `sync_published` outputs, reading only from `load()`/`values()` — never hard-coded digits.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_corpus_stats -v`
Expected: PASS

- [ ] **Step 5: Commit**

Run: `git add scripts/corpus_stats.py tests/test_corpus_stats.py && git commit -m "feat: corpus_stats renderers"`

---

### Task 4: `sync_published.py` — unified marker engine

**Files:**
- Modify: `scripts/sync_published.py`
- Test: `tests/test_sync_markers.py`

**Interfaces:**
- Consumes: `corpus_stats.RENDERERS`, `corpus_stats.values()` (Tasks 2–3).
- Produces: `MARKER: re.Pattern`, `resolve(name: str) -> str`, `sync_markers(text: str) -> tuple[str, list[str]]` returning `(new_text, unknown_names)`.

- [ ] **Step 1: Write the failing test**

```python
import sys; sys.path.insert(0, "scripts")
import sync_published as sp

def test_inline_and_block_resolve():
    text = "a <!-- sync:chunks -->0<!-- /sync:chunks --> b\n<!-- sync:gaps_table -->x<!-- /sync:gaps_table -->"
    out, unknown = sp.sync_markers(text)
    assert unknown == []
    assert "<!-- sync:chunks -->2,041<!-- /sync:chunks -->" in out
    assert "<!-- sync:gaps_table -->" in out and "x" not in out

def test_unknown_name_is_reported_not_silently_kept():
    out, unknown = sp.sync_markers("<!-- sync:nope -->1<!-- /sync:nope -->")
    assert unknown == ["nope"]

def test_idempotent():
    text = "<!-- sync:docs -->0<!-- /sync:docs -->"
    once, _ = sp.sync_markers(text)
    twice, _ = sp.sync_markers(once)
    assert once == twice
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_sync_markers -v`
Expected: FAIL — `AttributeError: module 'sync_published' has no attribute 'sync_markers'`

- [ ] **Step 3: Implement the engine and rewire `main`**

`MARKER = re.compile(r"<!-- sync:([A-Za-z0-9_]+) -->(.*?)<!-- /sync:\1 -->", re.S)`. `resolve` checks `RENDERERS` then `values()`, else raises `KeyError`. `sync_markers` returns the rewritten text plus any unknown names; `main` prints unknown names and sets the drift flag. Delete the old `REGIONS`/`FILES`/`sync_regions`; `--check` compares committed vs freshly rendered and exits 1 on any difference or unknown name.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_sync_markers -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

Run: `git add scripts/sync_published.py tests/test_sync_markers.py && git commit -m "feat: unified sync marker engine (renderers + scalars, fail-closed)"`

---

### Task 5: Convert the published docs (README, HF card, FAQ)

**Files:**
- Modify: `README.md`, `HF_DATASET_CARD.md`, `docs/FAQ.md`

**Interfaces:**
- Consumes: `sync_markers` (Task 4), `RENDERERS`/`values()` (Tasks 2–3).

- [ ] **Step 1:** Replace the existing `<!-- sync:headline -->`, `<!-- sync:stats -->`, `<!-- sync:gaps -->` regions with markers named `headline`, `stats_bullets`, `gaps_table`; add inline scalar markers (`chunks`, `docs`, `raw_mib`, `frameworks_present`) in the prose that restates them.

- [ ] **Step 2:** Run: `python scripts/sync_published.py --no-about --no-hf` then `python scripts/sync_published.py --check --no-about --no-hf`
Expected: rewrites once, then "in sync" (exit 0).

- [ ] **Step 3:** Run: `python -m unittest discover -s tests -v` and `python scripts/validate_sources.py`
Expected: PASS.

- [ ] **Step 4: Commit**

Run: `git add README.md HF_DATASET_CARD.md docs/FAQ.md && git commit -m "docs: source published numbers from the stats asset"`

---

### Task 6: Convert the reference docs (DATA_*, COOKBOOK, ARCHITECTURE)

**Files:**
- Modify: `docs/DATA_DICTIONARY.md`, `docs/DATA_PIPELINE.md`, `docs/COOKBOOK.md`, `docs/ARCHITECTURE.md`

**Interfaces:**
- Consumes: `values()`, `RENDERERS` (Tasks 2–3).

- [ ] **Step 1:** Apply the conversion rule — mark every number that changes between runs; leave structural constants (`512`, `50`, thresholds) as prose. Drop hard-coded **sample-output** lines inside fenced code blocks (COOKBOOK `# 2041 chunks · …`) rather than marking them (Global Constraint: no markers in code fences).

- [ ] **Step 2:** Run: `python scripts/sync_published.py --no-about --no-hf && python scripts/sync_published.py --check --no-about --no-hf`
Expected: in sync (exit 0).

- [ ] **Step 3:** Run the docs link checker: `python3 "/root/.commandcode/skills/docs-steward/scripts/check_doc_links.py" .`
Expected: no broken links in project docs.

- [ ] **Step 4: Commit**

Run: `git add docs/ && git commit -m "docs: source reference numbers from the stats asset"`

---

### Task 7: Convert the internal references (skill + ROADMAP)

**Files:**
- Modify: `.commandcode/skills/compliance-officer/references/project-context.md`, `.commandcode/skills/compliance-officer/references/framework-watchlist.md`, `docs/ROADMAP.md`

**Interfaces:**
- Consumes: `sync_markers` (Task 4).

- [ ] **Step 1:** Add `docs/ROADMAP.md` (and the two skill references that live under `docs/`-adjacent paths the tool is told about) to the file list `sync_published.main` iterates; add markers for the counts/gap list. **Leave the watchlist's per-framework status table hand-written** (spec: not a marker-friendly shape).

- [ ] **Step 2:** Run `python scripts/sync_published.py --no-about --no-hf && python scripts/sync_published.py --check --no-about --no-hf`
Expected: in sync (exit 0).

- [ ] **Step 3: Commit**

Run: `git add docs/ROADMAP.md .commandcode/skills/compliance-officer/references/ scripts/sync_published.py && git commit -m "docs: source skill + roadmap numbers from the stats asset"`

---

### Task 8: `verify_stats.py`, CI gates, and shipping

**Files:**
- Create: `scripts/verify_stats.py`
- Modify: `pixi.toml`, `.github/workflows/ci.yml`, `.github/workflows/monthly-release.yml`, `scripts/publish_hf.py`
- Test: `tests/test_corpus_stats.py` (append)

**Interfaces:**
- Produces: `verify_stats.main() -> int` (0 = consistent).

- [ ] **Step 1: Write the failing test**

```python
import sys; sys.path.insert(0, "scripts")
import verify_stats as vs

def test_stats_totals_match_artifacts():
    assert vs.check() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_corpus_stats -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'verify_stats'`

- [ ] **Step 3: Implement `verify_stats.py`**

`check() -> list[str]` returns mismatches (empty = OK): `corpus_stats.chunks` == parquet rows; `frameworks_present` == distinct stems; `manifest_ok/skipped/error` == manifest counts; every `gaps.csv` id has 0 chunks in the parquet. `main()` prints and returns 1 if non-empty.

- [ ] **Step 4: Wire tasks, gates, and shipping**

`pixi.toml`: `build-stats`, `verify-stats`, `test` (`python -m unittest discover -s tests -v`); add `build-stats` after `build-silver` in `pipeline`. `ci.yml`: add `build-stats` → `git diff --exit-code data/stats/` → `verify-stats` → existing `check-docs`. `monthly-release.yml`: run `build-stats`, zip `corpus-stats-<run>.zip` + copy `corpus_stats.csv` into `dist/`, add both to the release; `publish_hf.py` uploads the five CSVs.

- [ ] **Step 5: Run the full gate**

Run: `python -m unittest discover -s tests -v && python scripts/verify_stats.py && python scripts/sync_published.py --check --no-about --no-hf && python scripts/build_stats.py && git diff --exit-code data/stats/`
Expected: all pass.

- [ ] **Step 6: Commit**

Run: `git add scripts/verify_stats.py tests/ pixi.toml .github/workflows/ scripts/publish_hf.py && git commit -m "feat: verify-stats + CI gates + release/HF shipping for the stats asset"`

---

## Self-Review

- **Spec coverage:** every spec section maps to a task — asset (1), value map/renderers (2–3), markers (4), conversion (5–7), enforcement + shipping (8). The code-fence edge case is handled in Task 6, Step 1.
- **Step scan:** each step is one action with a checkable result; no "handle edge cases" lines; bodies appear only where an algorithm isn't determined by signature+tests (Task 1 collect order, Task 3 gaps grouping, Task 8 checks).
- **Type consistency:** `collect`/`write`/`values`/`load`/`RENDERERS`/`sync_markers`/`check` names and signatures are identical across the tasks that consume them.
- **Review Focus:** the five lines each get a test — (1) Task 4 test 2, (2) Task 4 tests 1–2, (3) Task 2 test 2, (4) Task 3 test 3, (5) Task 1 round-trip (csv quoting).
- **Proportion:** eight tasks, tests + signatures not transcripts; the plan argues from the spec rather than restating it.
