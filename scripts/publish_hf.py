#!/usr/bin/env python3
"""Publish Silver to Hugging Face Datasets — ponytail: one script, no new dep beyond huggingface_hub (already in pixi env)."""
import os
from pathlib import Path
from huggingface_hub import HfApi

REPO_ID = os.environ.get("HF_REPO_ID", "GauravGurjar/open-regulatory-corpus")
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
    # dated copy + latest for change detection (ponytail: 2 files, history via git log)
    import json, datetime
    run_id = os.environ.get("RUN_ID") or Path("data/silver/silver_stats.json").read_text()[:100] if Path("data/silver/silver_stats.json").exists() else ""
    try:
        stats = json.loads(Path("data/silver/silver_stats.json").read_text())
        run_id = stats.get("run_id", "").split("/")[-1] or os.environ.get("RUN_ID", "")
    except Exception:
        run_id = os.environ.get("RUN_ID", "")
    if not run_id or "/" in run_id:
        run_id = datetime.date.today().isoformat()
    # latest (for load_dataset)
    api.upload_file(
        path_or_fileobj=str(PARQUET),
        path_in_repo="data/compliance_chunks.parquet",
        repo_id=REPO_ID,
        repo_type="dataset",
        commit_message=f"chore: update Silver {run_id}",
    )
    # dated snapshot (detect changes, in snapshots/ so load_dataset still single file)
    api.upload_file(
        path_or_fileobj=str(PARQUET),
        path_in_repo=f"snapshots/compliance_chunks_{run_id}.parquet",
        repo_id=REPO_ID,
        repo_type="dataset",
        commit_message=f"chore: snapshot Silver {run_id}",
    )
    # stats with date (snapshots/)
    if Path("data/silver/silver_stats.json").exists():
        api.upload_file(
            path_or_fileobj="data/silver/silver_stats.json",
            path_in_repo=f"snapshots/silver_stats_{run_id}.json",
            repo_id=REPO_ID,
            repo_type="dataset",
        )
    # corpus statistics asset -> data/stats/<name>.csv
    stats_dir = Path("data/stats")
    if stats_dir.exists():
        for csv_path in sorted(stats_dir.glob("*.csv")):
            api.upload_file(
                path_or_fileobj=str(csv_path),
                path_in_repo=f"data/stats/{csv_path.name}",
                repo_id=REPO_ID,
                repo_type="dataset",
                commit_message=f"chore: update stats {run_id}",
            )
    if CARD.exists():
        api.upload_file(path_or_fileobj=str(CARD), path_in_repo="README.md", repo_id=REPO_ID, repo_type="dataset")
    print(f"published https://huggingface.co/datasets/{REPO_ID} (latest + dated {run_id})")

if __name__ == "__main__":
    main()
