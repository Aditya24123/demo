#!/usr/bin/env bash
set -euo pipefail
echo "health:"
curl -sS -m 8 http://127.0.0.1:8766/health
echo
echo "enrich:"
curl -sS -m 20 "http://127.0.0.1:8766/materials/mp-zw/enrich" -o /tmp/enrich.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/enrich.json"))
print("hit", d.get("cache_hit"), "desc", bool(d.get("description")), "spectra", (d.get("spectra") or {}).get("count"), "src", d.get("source"))
print("desc_preview", (d.get("description") or "")[:120])
PY
echo "details:"
curl -sS -m 30 "http://127.0.0.1:8766/materials/mp-zw/details?sections=thermo,electronic_structure,spectra&limit=8&downsample=true" -o /tmp/details.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/details.json"))
sp=d.get("details",{}).get("spectra",{})
print("spectra", sp.get("count"), "source", sp.get("source"))
print("groups", [(g.get("key"), g.get("available_count")) for g in (d.get("property_groups") or [])])
recs=sp.get("records") or []
if recs:
    s=recs[0].get("spectrum") or {}
    print("first_spectrum_x", len(s.get("x") or []), "y", len(s.get("y") or []))
PY
echo "workspace:"
curl -sS -m 15 "http://127.0.0.1:8766/materials/mp-zw/workspace" -o /tmp/ws.json
python3 - <<'PY'
import json
d=json.load(open("/tmp/ws.json"))
print("keys", list(d.keys())[:12])
print("desc", bool((d.get("summary") or {}).get("description")), "caps", d.get("capabilities"))
PY
