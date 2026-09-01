from pathlib import Path
import json
bronze = Path("data/bronze/latest")
if not bronze.exists():
    bronze = sorted(Path("data/bronze").glob("20*"), reverse=True)[0]
print(f"bronze={bronze}")
manifest = bronze / "manifest.jsonl"
lines = manifest.read_text().splitlines()
ok = [l for l in lines if '"status": "ok"' in l]
skipped = [l for l in lines if "skipped_public_only" in l]
errors = [l for l in lines if '"status": "error"' in l]
print(f"manifest lines: {len(lines)} ok={len(ok)} skipped={len(skipped)} errors={len(errors)}")
raw = list((bronze/"raw").glob("*"))
hdr = list((bronze/"headers").glob("*"))
print(f"raw files: {len(raw)} headers: {len(hdr)}")
assert len(ok) == len(raw) or len(ok) == len(hdr) or abs(len(raw)-len(hdr)) <=1, f"mismatch ok={len(ok)} raw={len(raw)} hdr={len(hdr)} (CJIS dup pdf+html allowed)"
assert len(skipped) == 8, f"expected 8 skipped got {len(skipped)}"
assert len(ok) >= 34, "need >=34 ok (all PDFs)"
print("BRONZE OK")
for p in raw[:3]:
    print(p, p.stat().st_size)
