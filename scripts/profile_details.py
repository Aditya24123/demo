from pathlib import Path
import time
from catalyst.local_store import LocalCatalystStore

s = LocalCatalystStore(Path.home() / "catalyst-live")
try:
    df = s.query_df("SELECT * FROM evidence_index WHERE material_id=? LIMIT 30", ["mp-zw"])
    print("evidence_index rows", len(df))
    if not df.empty:
        print(df.to_string())
except Exception as e:
    print("evidence_index err", type(e).__name__, e)

try:
    tables = s.query_df("SHOW TABLES")
    print("tables", list(tables.iloc[:, 0]) if not tables.empty else tables)
except Exception as e:
    print("tables err", e)

for sections in (
    ["thermo"],
    ["spectra"],
    ["bonds"],
    ["thermo", "electronic_structure", "magnetism", "elasticity", "dielectric", "bonds", "surfaces", "spectra"],
):
    t0 = time.time()
    d = s.material_details("mp-zw", sections=list(sections), limit=8, downsample=True)
    dt = (time.time() - t0) * 1000
    sp = (d or {}).get("details", {}).get("spectra", {}).get("count")
    print("sections", sections, f"{dt:.0f}ms", "spectra", sp)
