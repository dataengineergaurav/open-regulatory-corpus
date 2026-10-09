from pathlib import Path
import json

bronze = Path("data/bronze/latest")
if not bronze.exists():
    bronze = sorted(Path("data/bronze").glob("20*"), reverse=True)[0]
print(f"bronze={bronze}")

manifest = bronze / "manifest.jsonl"
rows = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
ok = [r for r in rows if r.get("status") == "ok"]
skipped = [r for r in rows if r.get("status") == "skipped_public_only"]
errors = [r for r in rows if r.get("status") == "error"]
print(f"manifest lines: {len(rows)} ok={len(ok)} skipped={len(skipped)} errors={len(errors)}")

sources = json.loads(Path("data/sources.json").read_text())
public_ids = [s["id"] for s in sources if s.get("public")]
expected_skipped = len(sources) - len(public_ids)
print(f"sources: {len(sources)} total, {len(public_ids)} public, {expected_skipped} paywalled")

raw = list((bronze / "raw").glob("*"))
hdr = list((bronze / "headers").glob("*"))
print(f"raw files: {len(raw)} headers: {len(hdr)}")

assert len(ok) == len(raw) or len(ok) == len(hdr) or abs(len(raw) - len(hdr)) <= 1, \
    f"mismatch ok={len(ok)} raw={len(raw)} hdr={len(hdr)} (CJIS dup pdf+html allowed)"
assert len(skipped) == expected_skipped, \
    f"expected {expected_skipped} skipped (public:false in sources.json), got {len(skipped)}"
# Derived floor: every public source should land at least one document (secondary
# PDFs only add to the count). Scales with the registry instead of a magic number.
assert len(ok) >= len(public_ids), \
    f"expected >= {len(public_ids)} ok (one per public source), got {len(ok)}"
print("BRONZE OK")
for p in raw[:3]:
    print(p, p.stat().st_size)
