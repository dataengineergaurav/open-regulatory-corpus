# Compliance Data — Bronze → Silver

Public-only corpus: **38 frameworks** → Bronze 58 raw (27 PDFs, 44M) → Silver `compliance_chunks.parquet` (1519 chunks × 512/50, 54 docs). Monthly Releases.

**Get data:** [Releases](https://github.com/dataengineergaurav/compliance-data/releases) — `compliance-silver-*.parquet` (1.6M) + `compliance-bronze-*.tar.gz` + `SHA256SUMS`. No crawl needed.

**What's inside (38 public, 8 skipped paywalled)**

| Domain | Frameworks |
|---|---|
| AI Governance (9) | NIST-AI-RMF, NIST-AI-600-1, EU-AI-ACT*, OMB-M25-21, OMB-M25-22, OWASP-LLM-2026, CO-AI, TX-TRAIGA, SG-MODEL-AI |
| Privacy & Data (8) | GDPR*, CCPA-CPRA, FERPA, COPPA, UK-DP-AI, BR-LGPD*, AU-PRIVACY-AI, DOJ-DSP |
| Cybersecurity (7) | NIST-CSF2, NIST-800-53, NIST-800-171, FEDRAMP, CMMC*, CJIS-6.1, IRS-1075 |
| Financial (6) | SOX, GLBA, NYDFS-500, FRB-MRM-2026, ECOA-REG-B, NAIC-AI |
| Health / Access / Trade (8) | HIPAA*, HHS-PART2*, SECTION-508, ONC-HTI1, FDA-AI-MD, NYC-LL144, IL-AIVIA*, EAR |

`*` 0 chunks in current Silver — WAF / JS wrapper filtered (see `docs/DATA_PIPELINE.md` Troubleshooting). Skipped: ISO-42001/42005/23894/38507/5338/24028, SOC2, PCI-DSS (paywalled, `skipped_public_only`).

**Stats (latest `data/silver/silver_stats.json:1`):** 1519 chunks / 54 docs. Largest: `CJIS-6.1` 466, `IRS-1075` 228, `SOX` 226, `FDA-AI-MD` 80, `EAR` 84. See `data/sources.json:46` for URLs.

**Use the data:**
```python
from datasets import load_dataset
ds = load_dataset("parquet", data_files="compliance_chunks.parquet")["train"]
# filter by framework
fda = ds.filter(lambda x: x["framework_id"] == "FDA-AI-MD")
# or with pandas
import pandas as pd
df = pd.read_parquet("compliance_chunks.parquet")
df[df.framework_id.str.startswith("NIST")].head()
```

**Run locally (fresh Bronze):**
```bash
pixi install
pixi run pipeline run_id=2026-09-01   # crawl → verify_bronze → build_silver → verify_silver
```

**Try without installing:** [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/dataengineergaurav/compliance-data/blob/main/notebooks/01_search.ipynb) · [Hugging Face](https://huggingface.co/datasets/dataengineergaurav/compliance-data) (after `HF_TOKEN` publish) · License: `MIT` (code) + `CC-BY-4.0` (data)

Docs: `docs/DATA_PIPELINE.md` · Sources: `data/sources.json` · Releases: `https://github.com/dataengineergaurav/compliance-data/releases`
