#!/usr/bin/env python3
"""Publish Silver to Hugging Face Datasets — ponytail: one script, no new dep beyond huggingface_hub (already in pixi env)."""
import os
from pathlib import Path
from huggingface_hub import HfApi

REPO_ID = os.environ.get("HF_REPO_ID", "dataengineergaurav/compliance-data")
PARQUET = Path("data/silver/compliance_chunks.parquet")
CARD = Path("HF_DATASET_CARD.md")  # optional

def main():
    if not PARQUET.exists():
        raise SystemExit(f"missing {PARQUET} — run pixi run build-silver first")
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        print("HF_TOKEN not set — dry run: showing what would be uploaded")
        print(f"  repo: {REPO_ID}")
        print(f"  file: {PARQUET} ({PARQUET.stat().st_size/1e6:.1f} MB)")
        print("  to publish: HF_TOKEN=hf_xxx python scripts/publish_hf.py")
        print("  or: huggingface-cli upload", REPO_ID, str(PARQUET), "--repo-type dataset")
        return
    api = HfApi(token=token)
    api.create_repo(REPO_ID, repo_type="dataset", exist_ok=True)
    api.upload_file(
        path_or_fileobj=str(PARQUET),
        path_in_repo="data/compliance_chunks.parquet",
        repo_id=REPO_ID,
        repo_type="dataset",
        commit_message="chore: update Silver 1519 chunks",
    )
    if CARD.exists():
        api.upload_file(path_or_fileobj=str(CARD), path_in_repo="README.md", repo_id=REPO_ID, repo_type="dataset")
    print(f"published https://huggingface.co/datasets/{REPO_ID}")

if __name__ == "__main__":
    main()
