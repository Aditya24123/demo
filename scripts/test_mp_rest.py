#!/usr/bin/env python3
import json
import os
import urllib.parse
import urllib.request

key = open(os.path.expanduser("~/catalyst-live/.secrets/mp_api_key")).read().strip()


def get(path, params=None):
    q = urllib.parse.urlencode(params or {}, doseq=True)
    url = f"https://api.materialsproject.org{path}"
    if q:
        url += f"?{q}"
    req = urllib.request.Request(url, headers={"X-API-KEY": key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


# formula search
s = get("/materials/summary/", {"formula": "CdS", "_limit": 5, "_fields": "material_id,formula_pretty,energy_above_hull,is_stable"})
print("formula hits:")
for d in s.get("data") or []:
    print(" ", d.get("material_id"), d.get("formula_pretty"), d.get("is_stable"), d.get("energy_above_hull"))

mid = (s.get("data") or [{}])[0].get("material_id")
print("pick", mid)

if mid:
    x = get("/materials/xas/", {"material_ids": mid, "_limit": 3})
    print("xas count", len(x.get("data") or []), "meta", x.get("meta"))
    r = get("/materials/robocrys/", {"material_ids": mid, "_limit": 1, "_fields": "material_id,description"})
    desc = ((r.get("data") or [{}])[0].get("description") or "")[:160]
    print("robo", desc)
