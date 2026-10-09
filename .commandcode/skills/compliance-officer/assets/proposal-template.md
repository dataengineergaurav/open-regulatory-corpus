# Corpus Enhancement Proposal — <scope> — <YYYY-MM-DD>

> Review-only. Nothing below has been applied. Verify every source against its authoritative URL.
> Not legal advice.

## 1. Scope & assumptions

- **Scope:** <frameworks / domain / whole corpus>
- **Shapes run:** <gap-recovery | currency-check | new-source | full-sweep>
- **Assumptions:** <what you assumed when the request was ambiguous>
- **Out of scope:** <what you deliberately did not cover, and why>

## 2. State snapshot

From `scripts/state_snapshot.py` (run `<run_id>`):

- Sources: **<N>** total = **<public>** public + **<skipped>** skipped
- Silver: **<chunks>** chunks across **<docs>** documents, **<present>/<public>** frameworks present
- Manifest: **<ok>** ok · **<skipped>** skipped · **<error>** error
- **Gap list (0 chunks):** `<ID>`, `<ID>`, …

## 3. Current-affairs findings

One row per framework in scope. "Change" is what actually changed; "Action" is your recommendation.

| Framework | Current version / date | Change since last run | Authoritative URL | Action |
|---|---|---|---|---|
| `<ID>` | <version / effective date, or "could not verify"> | <new revision / amendment / new guidance / none / URL moved> | <url> | <keep / update URL / re-crawl / flag> |

**Signals to note explicitly:** new revision or effective date · regulation entering force · new or
amended guidance/RMF · agency rename · URL migration · deprecation/supersession.

## 4. Source proposals

Ranked by value = (chunks recovered/added) × (authority) ÷ (fetch risk).

| # | id | url | public | domain | type | rationale | fetch risk | expected outcome |
|---|---|---|---|---|---|---|---|---|
| 1 | `<ID>` | <url> | true | <domain> | html/pdf | <why this fixes/adds> | low/med/high | <≈N chunks / replaces shell> |
| 2 | … | … | … | … | … | … | … | … |

For each proposal, state **how you verified** it (fetched → saw text; compared versions; confirmed
publisher). If unverified, mark **needs human verification** and say why.

## 5. Ready-to-apply diff (`data/sources.json`)

Exact JSON objects, in file order. New entries go in their domain's cluster; replacements show the
old value in a comment above. Keep the array valid JSON (watch trailing commas).

```jsonc
// REPLACE existing entry
{"id": "EU-AI-ACT", "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:32024R1689", "public": true},

// ADD (AI Governance cluster)
{"id": "NEW-ID", "url": "https://…", "public": true},
```

## 6. Impact & risks

- **Verifier invariants:** does this change the **8 skipped** count or the **≥34 ok** floor? If yes, flag it (CI will fail otherwise). Adding a paywalled entry breaks `verify_bronze`.
- **Published surfaces:** chunk/source totals feed `README.md` + `HF_DATASET_CARD.md`; `check-docs` will drift until `sync-published` runs.
- **Licensing/ethics:** confirm every proposed source is public and legally fetchable (public-only rule).
- **Politeness:** no proposal should bypass robots.txt, a WAF, or a JS shell by evasion.
- **Corpus distribution:** note if a proposal would further concentrate chunks in the top documents.

## 7. Suggested next steps (for a human — do not run)

```bash
pixi run pipeline run_id=<YYYY-MM-DD>   # apply + re-crawl
pixi run verify                          # verify-bronze + verify-silver
pixi run check-docs                      # confirm published numbers
pixi run sync-published                  # if numbers moved
```

Also: open a PR with the one-line (or one-object) `sources.json` change per framework.
