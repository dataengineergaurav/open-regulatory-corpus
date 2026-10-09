#!/usr/bin/env python3
"""Build a balanced corpus slice: cap each framework's contribution.

The full Silver corpus is heavily skewed — CJIS-6.1 + IRS-1075 + SOX are ~55% of all
chunks (CJIS-6.1 alone ~30%). This writes a companion parquet where no framework
contributes more than `--cap` chunks, so downstream training/eval isn't dominated by
the big three. The full corpus is untouched.

Usage:
  python scripts/build_balanced_slice.py [--cap 30] [--seed 0]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SILVER = ROOT / "data/silver/compliance_chunks.parquet"


def main() -> int:
    ap = argparse.ArgumentParser(description="Cap each framework's chunks to build a balanced slice.")
    ap.add_argument("--cap", type=int, default=30, help="max chunks per framework (default 30)")
    ap.add_argument("--seed", type=int, default=0, help="sampling seed (deterministic output)")
    ap.add_argument("--out", default="data/silver/balanced_slice.parquet")
    args = ap.parse_args()

    df = pd.read_parquet(SILVER)
    df["stem"] = df.framework_id.str.split("_pdf").str[0]
    sampled = [g.sample(min(len(g), args.cap), random_state=args.seed) for _, g in df.groupby("stem")]
    balanced = pd.concat(sampled).reset_index(drop=True)

    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    balanced.drop(columns=["stem"]).to_parquet(out, index=False)

    stats = {
        "source": "data/silver/compliance_chunks.parquet",
        "cap": args.cap,
        "seed": args.seed,
        "chunks": int(len(balanced)),
        "frameworks": int(balanced.stem.nunique()),
        "max_per_framework": int(balanced.stem.value_counts().max()),
    }
    out.with_suffix(".json").write_text(json.dumps(stats, indent=2))
    print(f"{stats['chunks']} chunks · {stats['frameworks']} frameworks · "
          f"max {stats['max_per_framework']} per framework")
    print(f"wrote {out} and {out.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
