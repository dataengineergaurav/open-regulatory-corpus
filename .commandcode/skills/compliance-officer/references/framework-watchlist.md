# Framework Watchlist

Every source the corpus tracks, by domain, with its current URL, status, and **what to watch**.
This is your starting map for Step 2 (current affairs) and Step 3 (source analysis).

- URLs mirror `data/sources.json` at the current run (`<!-- sync:run_id -->2026-10-09<!-- /sync:run_id -->`). Always re-read the live file —
  it is the source of truth and may have changed.
- **Status** legend: `ok` = yields chunks · `gap` = public but 0 chunks · `skipped` = paywalled.
  Statuses move between runs (a site can start blocking, or a mirror can recover one), so always
  check the current run before reporting.
- "Watch for" items are *things to check*, not claims that they exist. Verify before reporting.

---

## AI Governance

| id | public | status | watch for |
|---|---|---|---|
| `NIST-AI-RMF` | ✅ | ok | RMF revisions; new companion profiles (e.g. the Generative-AI profile `NIST-AI-600-1`); crosswalks. |
| `NIST-AI-600-1` | ✅ | ok | Updates to the GenAI profile; new NIST AI publications. |
| `EU-AI-ACT` | ✅ | ok | Delegated/Implementing Acts, harmonised standards, codes of practice, phased application dates. |
| `OMB-M25-21` | ✅ | ok | Superseding OMB memoranda; administration changes to federal AI policy. |
| `OMB-M25-22` | ✅ | ok | Superseding OMB memoranda; federal AI acquisition guidance. |
| `OWASP-LLM-2026` | ✅ | ok | The next annual GenAI/LLM Top 10 version; new OWASP GenAI resources. |
| `CO-AI` | ✅ | ok | Colorado AG guidance/rulemaking under the Colorado AI Act; effective-date changes. |
| `TX-TRAIGA` | ✅ | ok | TRAIGA amendments; Texas legislature activity. |
| `SG-MODEL-AI` | ✅ | **gap** | Singapore IMDA/PDPC Model AI Governance Framework revisions; a source that isn't WAF-blocked. See gap leads below. |

## Privacy & Data

| id | public | status | watch for |
|---|---|---|---|
| `GDPR` | ✅ | ok | Corrective/implementing measures; EDPB guidance. |
| `CCPA-CPRA` | ✅ | ok | CPPA regulations updates; new CCPA/CPRA rulemaking. |
| `FERPA` | ✅ | ok | Department of Education FERPA regs/guidance changes. |
| `COPPA` | ✅ | ok | FTC COPPA Rule amendments; enforcement guidance. |
| `UK-DP-AI` | ✅ | ok | ICO AI/data-protection guidance revisions; UK data-reform legislation. |
| `BR-LGPD` | ✅ | **gap** | ANPD regulation updates; an English, statically-served LGPD text. See gap leads below. |
| `AU-PRIVACY-AI` | ✅ | ok | OAIC guidance on AI and privacy; Privacy Act reform. |
| `DOJ-DSP` | ✅ | ok | DOJ bulk-sensitive-data rule status and any vacatur/amendment. |

## Cybersecurity

| id | public | status | watch for |
|---|---|---|---|
| `NIST-CSF2` | ✅ | ok | CSF 2.0 revisions; new informative references. |
| `NIST-800-53` | ✅ | ok | SP 800-53 revision/update releases (r5 updates). |
| `NIST-800-171` | ✅ | ok | SP 800-171 revision releases (r3 / next). |
| `FEDRAMP` | ✅ | ok | FedRAMP baseline revisions; program modernization. |
| `CMMC` | ✅ | ok | CMMC program rule updates; the authoritative DoD surface (now served via eCFR mirror). |
| `CJIS-6.1` | ✅ | ok | New CJIS Security Policy version (annual); version-number/date changes. |
| `IRS-1075` | ✅ | ok | IRS Safeguards/Publication 1075 revisions. |

## Financial

| id | public | status | watch for |
|---|---|---|---|
| `SOX` | ✅ | ok | SEC rulemaking under SOX; PCAOB standard changes. |
| `GLBA` | ✅ | ok | FTC Safeguards Rule amendments; enforcement guidance. |
| `NYDFS-500` | ✅ | **gap** | NYDFS Part 500 amendments and guidance letters; a fetchable source. See gap leads below. |
| `FRB-MRM-2026` | ✅ | ok | Federal Reserve SR letters superseding SR 26-2 / MRM guidance. |
| `ECOA-REG-B` | ✅ | **gap** | CFPB guidance on AI/algorithmic credit decisions; a fetchable source. See gap leads below. |
| `NAIC-AI` | ✅ | **gap** | NAIC model bulletin adoption; a fetchable source. See gap leads below. |

## Health / Access / Trade

| id | public | status | watch for |
|---|---|---|---|
| `HIPAA` | ✅ | ok | Privacy/Security Rule amendments (now served via the eCFR mirror). |
| `HHS-PART2` | ✅ | ok | Part 2 final rule updates (now served via the eCFR mirror). |
| `SECTION-508` | ✅ | ok | Revised Section 508 standards; Access Board updates. |
| `ONC-HTI1` | ✅ | ok | HTI rule updates (HTI-2 etc.); ONC certification program changes. |
| `FDA-AI-MD` | ✅ | ok | FDA AI/ML medical-device guidance and device list updates. |
| `NYC-LL144` | ✅ | ok | DCWP enforcement, FAQs, and rule amendments. |
| `IL-AIVIA` | ✅ | ok | Amendments to the Illinois AI Video Interview Act. |
| `EAR` | ✅ | ok | BIS EAR revisions; new export-control rules. |

## Paywalled — tracked, never fetched (`public: false`)

Do **not** propose fetching these. The skipped count in `verify_bronze` is derived from
`public: false`, so adding another paywalled source **changes** that expectation (call it out).

`ISO-42001` · `ISO-42005` · `ISO-23894` · `ISO-38507` · `ISO-5338` · `ISO-24028` · `SOC2` · `PCI-DSS`

---

## Gap leads (starting points, verify before proposing)

From `docs/DATA_PIPELINE.md#troubleshooting`. These are *leads*, not verified fixes — fetch and
confirm the served bytes are real document text.

**Already recovered via configured `mirrors`** (verified to serve text): `GDPR`
(legislation.gov.uk), `EU-AI-ACT` (Consilium document server), `HIPAA` / `HHS-PART2` (eCFR),
`CMMC` (eCFR), and `IL-AIVIA` (which became reachable). That is the pattern to follow: add an
authoritative alternate URL to `mirrors` rather than mutating the canonical `url`.

**Still open:** the live list is `data/stats/gaps.csv` — the weekly gap watch tracks it.

| Framework | Blocker | Lead to try |
|---|---|---|
| `NYDFS-500` | Non-200 from `dfs.ny.gov` | Try an alternate NYDFS surface or the codified text on a stable host. |
| `ECOA-REG-B` | Non-200 from the CFPB archive URL | Try the live CFPB Regulation B page or eCFR (12 CFR Part 1002). |
| `NAIC-AI` | Non-200 from `content.naic.org` | Try the NAIC model-bulletin page on a stable host, or a state insurance bulletin. |
| `SG-MODEL-AI` | Landed a WAF challenge | Try a non-`pdpc.gov.sg` mirror or the IMDA-hosted framework document. |
| `BR-LGPD` | "PDF" URL returns an HTML wrapper, and the only static source is Portuguese | Find an English, statically-served LGPD text (the corpus is English-only). |

When you verify a replacement, note **what it is** (HTML vs PDF), the **effective/version date**,
and whether the bytes are stable (a register page that re-renders is fine if text is present).

## Candidate-source criteria

A new framework is worth proposing when it:

1. Belongs to one of the five domains above.
2. Is **freely and legally** fetchable (public register, agency site, official gazette).
3. Governs a distinct topic the corpus does not already cover (avoid near-duplicates of tracked frameworks).
4. Has an authoritative URL that **serves text** (verified by fetch), not a JS shell or WAF page.

Record for each: proposed `id`, `url`, `public`, `domain`, rationale, fetch risk, expected outcome.
