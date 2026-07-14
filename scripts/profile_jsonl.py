from pathlib import Path
import time
import duckdb

root = Path.home() / "catalyst-live/data/processed/catalyst/v2025.09.25"
thermo = root / "material_thermo.jsonl"
spectra = root / "material_spectra.jsonl"
mid = "mp-zw"

con = duckdb.connect()
for label, path in [("thermo", thermo), ("spectra", spectra)]:
    t0 = time.time()
    try:
        df = con.execute(
            """
            SELECT *
            FROM read_json_auto(?, format='newline_delimited', ignore_errors=true)
            WHERE CAST(material_id AS VARCHAR) = ?
            LIMIT 8
            """,
            [str(path), mid],
        ).df()
        print(label, "duckdb", f"{(time.time()-t0)*1000:.0f}ms", "rows", len(df))
    except Exception as e:
        print(label, "duckdb FAIL", type(e).__name__, e, f"{(time.time()-t0)*1000:.0f}ms")
