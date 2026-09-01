from pathlib import Path
import pyarrow.parquet as pq
p = Path("data/silver/compliance_chunks.parquet")
assert p.exists(), "missing silver"
t = pq.read_table(str(p))
print(f"rows={t.num_rows} cols={t.column_names}")
assert t.num_rows >= 300, f"expected >=300 chunks got {t.num_rows}"
# check avg token
import json
print(t.slice(0,1).to_pylist()[:1])
print("SILVER OK")
