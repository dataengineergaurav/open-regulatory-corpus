---
license: cc-by-4.0
task_categories: [feature-extraction, text-retrieval]
tags: [compliance, ai-governance, nist, gdpr, rag, bronze-silver]
pretty_name: Compliance Data — Bronze → Silver
---

# Compliance Data — Bronze → Silver

Public-only corpus: 38 frameworks → Bronze 58 raw (27 PDFs, 44M) → Silver `compliance_chunks.parquet` (1519 chunks × 512/50, 54 docs). From [dataengineergaurav/compliance-data](https://github.com/dataengineergaurav/compliance-data) (monthly Releases).

## What's inside

| Domain | Frameworks |
|---|---|
| AI Governance | NIST-AI-RMF, NIST-AI-600-1, EU-AI-ACT*, OMB-M25-21, OMB-M25-22, OWASP-LLM-2026, CO-AI, TX-TRAIGA, SG-MODEL-AI |
| Privacy | GDPR*, CCPA-CPRA, FERPA, COPPA, UK-DP-AI, BR-LGPD*, AU-PRIVACY-AI, DOJ-DSP |
| Cybersecurity | NIST-CSF2, NIST-800-53, NIST-800-171, FEDRAMP, CMMC*, CJIS-6.1, IRS-1075 |
| Financial | SOX, GLBA, NYDFS-500, FRB-MRM-2026, ECOA-REG-B, NAIC-AI |
| Health/Access/Trade | HIPAA*, HHS-PART2*, SECTION-508, ONC-HTI1, FDA-AI-MD, NYC-LL144, IL-AIVIA*, EAR |

`*` 0 chunks — WAF/JS wrapper filtered. Skipped (paywalled): ISO-42001/42005/23894/38507/5338/24028, SOC2, PCI-DSS.

Stats: 1519 chunks / 54 docs. Largest: CJIS-6.1 466, IRS-1075 228, SOX 226. Provenance: `framework_id, chunk_id, text, source, kind, token_est, sha256`.

## Use

```python
from datasets import load_dataset
ds = load_dataset("GauravGurjar/compliance-data")["train"]
# or
import pandas as pd
df = pd.read_parquet("data/compliance_chunks.parquet")
df[df.framework_id == "FDA-AI-MD"].head()
```

See `notebooks/01_search.ipynb` for TF-IDF search without GPU (Colab).

## License

Code MIT, data CC-BY-4.0 where applicable. Sources retain original terms. Not legal advice. See `data/sources.json` for URLs.
