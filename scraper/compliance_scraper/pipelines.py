import hashlib, json, time
from pathlib import Path

class RawPipeline:
    def open_spider(self, spider):
        ts = time.strftime("%Y-%m-%d_%H%M")
        self.run_id = getattr(spider, "run_id", ts)
        # resolve repo root (scraper/ -> ..)
        self.repo_root = Path(__file__).resolve().parents[2]
        self.base = self.repo_root / "data" / "bronze" / self.run_id
        (self.base / "raw").mkdir(parents=True, exist_ok=True)
        (self.base / "headers").mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.base / "manifest.jsonl"
        # init manifest with skipped public_only (no request)
        import json as _json
        sources = _json.loads((self.repo_root / "data/sources.json").read_text())
        skipped = [s for s in sources if not s["public"]]
        with open(self.manifest_path, "w") as f:
            for s in skipped:
                f.write(_json.dumps({"id": s["id"], "url": s["url"], "status": "skipped_public_only", "reason": "paywalled/gated, public-only mode"}) + "\n")

    def process_item(self, item, spider):
        raw_dir = self.base / "raw"
        hdr_dir = self.base / "headers"
        # ensure base exists (err path may create manifest earlier)
        self.base.mkdir(parents=True, exist_ok=True)
        raw_dir.mkdir(parents=True, exist_ok=True)
        hdr_dir.mkdir(parents=True, exist_ok=True)
        iid = item["id"]
        body = item["body"]
        # ext from magic + content-type (ponytail: correct ext or it lies)
        ct = item.get("content_type", "")
        is_pdf_magic = body[:4] == b"%PDF"
        is_pdf_ct = "pdf" in ct.lower()
        is_pdf_url = item["url"].lower().endswith(".pdf") or ".pdf" in item["url"].lower()
        if is_pdf_magic or is_pdf_ct:
            ext = ".pdf"
        elif is_pdf_url and not is_pdf_magic and b"<html" in body[:2000].lower():
            ext = ".html"  # pdf url returned html wrapper
        else:
            ext = ".pdf" if is_pdf_url else ".html"
        (raw_dir / f"{iid}{ext}").write_bytes(body)
        (hdr_dir / f"{iid}.json").write_text(json.dumps({
            "id": iid, "url": item["url"], "final_url": item.get("final_url", item["url"]),
            "status": item.get("status", 200), "content_type": ct,
            "headers": item.get("headers", {}), "fetched_at": item.get("fetched_at"), "bytes": len(body)
        }, indent=2))
        # manifest line
        sha = hashlib.sha256(body).hexdigest()
        with open(self.manifest_path, "a") as f:
            f.write(json.dumps({"id": iid, "url": item["url"], "status": "ok", "content_type": ct, "bytes": len(body), "sha256_raw": sha, "fetched_at": item.get("fetched_at")}) + "\n")
        return item

    def close_spider(self, spider):
        # stats
        try:
            stats = spider.crawler.stats.get_stats() if hasattr(spider, "crawler") and hasattr(spider.crawler, "stats") else {}
        except Exception:
            stats = {}
        (self.base / "scrapy_stats.json").write_text(json.dumps(stats, indent=2, default=str))
        # latest symlink
        latest = self.repo_root / "data" / "bronze" / "latest"
        try:
            if latest.is_symlink() or latest.exists():
                latest.unlink()
            latest.symlink_to(self.run_id)
        except Exception:
            pass
