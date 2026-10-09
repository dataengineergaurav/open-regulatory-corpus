# Loop Variants — Recurring Compliance Runs

This project changes on a **regulatory clock** (months to years), not a machine clock. A
self-paced loop can only pace itself between 60s and 1 hour, so it is the wrong tool here. Every
variant below uses a **fixed cron cadence** and should be created **durable** so it survives
restarts. A loop supplies three things a one-off run does not: the **cadence**, a **deterministic
baseline** to diff against, and the rule to **report only deltas**.

Each variant maps to a task shape the skill already performs (Step 1 of `SKILL.md`). The loop is
just the schedule around that shape.

## Non-negotiables for every variant

1. **Politeness.** The project obeys `robots.txt`, autothrottles, caps concurrency at 2, and keeps
   a 7-day HTTP cache. A loop must not fire raw `web_fetch` at 38 government hosts on a timer —
   reuse the project's scraper/cache, or use **conditional requests** (`If-Modified-Since` /
   `If-None-Match` from `headers/<ID>.json`). A loop is not an excuse to hammer.
2. **Review-only.** Loops surface deltas and produce proposals. They never edit `data/sources.json`,
   run `pipeline` / `publish` / `sync-published`, or commit. The human apply step stays.
3. **Silent when nothing changed.** If a run finds no delta, it must report a single
   "no change" and stop — not re-summarize the whole corpus. Use the loop's noop path.
4. **Deterministic baseline.** Each variant names the artifact it diffs against (the manifest, the
   previous release, a cursor file). Without one, "changed" is undefined.
5. **Fixed cadence + durable.** Use cron, not self-pacing.

## How to start one

```
/loop 0 6 * * 1  Run the compliance-officer gap-recovery watch. …   # fixed cron cadence
```

or schedule it as a durable job (`cron_create` with a cron expression and `durable: true`). Do not
use a bare self-paced `/loop` — the 60–3600s clamp cannot express a weekly or monthly watch.

---

## Variant A — Gap-recovery watcher  ★ start here

- **Objective:** detect the moment one of the 7 empty frameworks starts serving real text.
- **Shape:** `gap-recovery` · **Cadence:** weekly — `0 6 * * 1`.
- **Watches:** `BR-LGPD`, `CMMC`, `EU-AI-ACT`, `GDPR`, `HHS-PART2`, `HIPAA`, `IL-AIVIA`.
- **Baseline:** the first probe's per-framework verdict; store it in a cursor file (below).
- **Loop prompt:**
  > Run the compliance-officer skill in `gap-recovery` mode for the 7 zero-chunk frameworks
  > (BR-LGPD, CMMC, EU-AI-ACT, GDPR, HHS-PART2, HIPAA, IL-AIVIA). Probe each with a polite
  > conditional fetch (obey robots.txt; one request per host). Decide whether the URL now serves
  > real document text — not a JS shell, WAF challenge, or nav wrapper. Report ONLY frameworks
  > whose verdict changed since the last probe; if none changed, reply "no change" and stop.
  > Never edit sources.json.
- **Success signal:** a framework flips shell/403 → real text → hand to `/compliance-officer
  gap-recovery` for a full proposal.
- **Guardrail:** a `200` that is still a shell is **not** a recovery. Verify served bytes.
- **Why first:** serves roadmap item #1 ("a shrinking missing set is progress"), tiny surface,
  near-zero noise — fires meaningfully a few times a year, not weekly.

## Variant B — Post-release currency digest

- **Objective:** catch amendments, effective-date changes, new guidance, and URL moves that the
  crawler re-ingests silently.
- **Shape:** `currency-check` · **Cadence:** monthly, the day after the release (`0 2 1 * *`)
  → `0 6 2 * *`.
- **Watches:** all 38 public frameworks.
- **Baseline:** the previous run's `run_id` and `manifest.jsonl`.
- **Loop prompt:**
  > Run `/compliance-officer currency-check` over all 38 public frameworks. Compare against the
  > previous release. Report only frameworks whose current version, effective date, or URL changed,
  > each with its authoritative URL. If nothing changed, reply "no change".
- **Why:** rides the cadence the project already commits to; monthly is cheap and low-noise.

## Variant C — Document drift detector

- **Objective:** flag sources whose bytes changed without a version bump — roadmap item #4.
- **Shape:** `drift-check` · **Cadence:** weekly — `0 5 * * 1`.
- **Watches:** every `ok` source's live content vs `sha256_raw` in `data/bronze/latest/manifest.jsonl`.
- **Baseline:** the manifest's `sha256_raw`, plus `Last-Modified` / `ETag` from `headers/<ID>.json`.
- **Loop prompt:**
  > Run `/compliance-officer drift-check`. For each public source, issue a conditional GET using the
  > `If-Modified-Since` / `If-None-Match` values from `headers/<ID>.json`. Flag only documents whose
  > bytes differ from the `sha256_raw` in `data/bronze/latest/manifest.jsonl`. Report changed
  > documents with their old/new hash and URL; if none, reply "no change".
- **Guardrail:** **conditional requests only** — never a full 38-URL download on a timer. A `304`
  means no drift and needs no body.

## Variant D — New-source scout  (optional, low frequency)

- **Objective:** surface newly enacted/updated regulations not yet in the registry.
- **Shape:** `new-source` (candidate discovery) · **Cadence:** quarterly — `0 8 1 */3 *`.
- **Watches:** the five domains, against candidate-source criteria in `references/framework-watchlist.md`.
- **Loop prompt:**
  > Run the compliance-officer skill in `new-source` mode across the five domains. Surface
  > regulations enacted or updated since the last scout that are public, freeze-fetchable, and not
  > already in `sources.json`. Report candidates with proposed id, url, public, domain, rationale,
  > and fetch risk. If there are none, reply "no change".
- **Why low frequency:** highest noise of the four; quarterly keeps it signal-rich.

---

## Cadence at a glance

| Variant | Shape | Cron | Frequency | Noise |
|---|---|---|---|---|
| A — Gap-recovery watcher | `gap-recovery` | `0 6 * * 1` | weekly | very low |
| B — Post-release currency digest | `currency-check` | `0 6 2 * *` | monthly | low |
| C — Document drift detector | `drift-check` | `0 5 * * 1` | weekly | medium |
| D — New-source scout | `new-source` | `0 8 1 */3 *` | quarterly | high |

**Recommended rollout:** start with **A** alone — best value-to-noise, proves the pattern. Add
**B** to align with the existing monthly release. Add **C** only once conditional-request
politeness is wired. Treat **D** as occasional, not ambient.

## Cursor / baseline state

Durable loops need a baseline that outlives a session. In order of preference:

1. **Existing artifacts** — `data/bronze/latest/manifest.jsonl` (has `sha256_raw`) is the natural
   baseline for Variants B and C; no new file needed.
2. **A cursor file** for the delta cursor (Variant A's last verdicts, Variant D's last scout date).
   Keep it out of the tracked repo — the session scratchpad for ad-hoc loops, or a dedicated
   dotfile if the loop is durable and shared.

Do not invent a new artifact when an existing one already answers "what changed".
