import json, time
from pathlib import Path
import scrapy

class GenericSpider(scrapy.Spider):
    name = "compliance"
    def __init__(self, run_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.run_id = run_id or time.strftime("%Y-%m-%d_%H%M")

    def start_requests(self):
        repo_root = Path(__file__).resolve().parents[3]
        sources = json.loads((repo_root / "data/sources.json").read_text())
        for s in sources:
            if not s["public"]:
                continue
            url = s["url"]
            # eur-lex displayAll hint
            if "eur-lex.europa.eu" in url and "?" not in url:
                url = url.replace("/eng", "/eng?displayAll=true")
            yield scrapy.Request(url, callback=self.parse, errback=self.err, meta={"id": s["id"], "orig_url": s["url"]}, dont_filter=True)

    async def start(self):
        for r in self.start_requests():
            yield r

    def parse(self, response):
        headers = {k.decode() if isinstance(k, bytes) else k: (v[0].decode() if isinstance(v[0], bytes) else v[0]) for k, v in response.headers.items()}
        ct = headers.get("Content-Type", "")
        body = response.body
        iid = response.meta["id"]
        orig = response.meta["orig_url"]
        # Fix CJIS /view -> true pdf: if html viewer and url contains /view and id is CJIS, yield item and also follow true pdf
        is_pdf_url = orig.lower().endswith(".pdf") or ".pdf/" in orig or orig.lower().endswith(".pdf/view")
        is_html_body = b"<html" in body[:2000].lower() if body else False
        # If pdf url returned html, try to discover pdf link(s) in body
        if is_pdf_url and ("text/html" in ct or is_html_body):
            # try direct pdf without /view for CJIS
            if iid == "CJIS-6.1" and orig.endswith("/view"):
                true_pdf = orig.replace("/view", "")
                yield scrapy.Request(true_pdf, callback=self.parse_pdf, errback=self.err, meta={"id": iid, "orig_url": orig, "is_extra": False}, dont_filter=True)
            # also discover pdf href in html (for BR-LGPD etc) - only path ends with .pdf
            try:
                hrefs = response.css("a::attr(href)").getall()
                seen = set()
                for h in hrefs:
                    base = h.lower().split("?")[0].split("#")[0]
                    if base.endswith(".pdf") and h not in seen:
                        seen.add(h)
                        pdf_url = response.urljoin(h)
                        if pdf_url.startswith("http"):
                            yield scrapy.Request(pdf_url, callback=self.parse_pdf, errback=self.err, meta={"id": f"{iid}_pdf{len(seen)}", "orig_url": pdf_url, "is_extra": True, "parent": iid}, dont_filter=True)
                        if len(seen) >= 3:
                            break
            except Exception:
                pass
        # For html sources, also discover up to 2 linked PDFs (secondary, same host, path ends pdf)
        if not is_pdf_url and "text/html" in ct:
            try:
                hrefs = response.css("a::attr(href)").getall()
                seen = set()
                for h in hrefs:
                    base = h.lower().split("?")[0].split("#")[0]
                    if base.endswith(".pdf") and h not in seen:
                        seen.add(h)
                        pdf_url = response.urljoin(h)
                        if pdf_url.startswith("http") and response.url.split("/")[2] in pdf_url:
                            yield scrapy.Request(pdf_url, callback=self.parse_pdf, errback=self.err, meta={"id": f"{iid}_pdf{len(seen)}", "orig_url": pdf_url, "is_extra": True, "parent": iid}, dont_filter=True)
                        if len(seen) >= 2:
                            break
            except Exception:
                pass
        # always yield original
        yield {
            "id": iid,
            "url": orig,
            "final_url": response.url,
            "status": response.status,
            "content_type": ct,
            "headers": headers,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "body": body,
        }

    def parse_pdf(self, response):
        headers = {k.decode() if isinstance(k, bytes) else k: (v[0].decode() if isinstance(v[0], bytes) else v[0]) for k, v in response.headers.items()}
        ct = headers.get("Content-Type", "")
        # only accept pdf-ish
        body = response.body
        if body[:4] != b"%PDF" and "pdf" not in ct.lower():
            # not a pdf, ignore extra
            if response.meta.get("is_extra"):
                return
        yield {
            "id": response.meta["id"],
            "url": response.meta["orig_url"],
            "final_url": response.url,
            "status": response.status,
            "content_type": ct,
            "headers": headers,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "body": body,
        }

    def err(self, failure):
        req = failure.request
        # log to manifest as error (append via pipeline? write directly)
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        repo_root = Path(__file__).resolve().parents[3]
        base = repo_root / "data" / "bronze" / self.run_id
        base.mkdir(parents=True, exist_ok=True)
        # ensure headers dir
        (base / "headers").mkdir(exist_ok=True)
        iid = req.meta.get("id", "unknown")
        import json as _json
        with open(base / "manifest.jsonl", "a") as f:
            f.write(_json.dumps({"id": iid, "url": req.meta.get("orig_url", req.url), "status": "error", "error": str(failure.value), "fetched_at": ts}) + "\n")
