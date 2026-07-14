"""Selected-material Materials Project enrichment (local-first, cache-on-read).

Hard rule: never bulk-query MP. Only enrich the single material being opened.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from catalyst.settings import local_root
from catalyst.util import to_jsonable

_MP_ID_RE = re.compile(r"^mp-\d+$", re.IGNORECASE)
_CACHE_VERSION = 1


def mp_cache_dir(repo_root: Path) -> Path:
    path = local_root(repo_root) / "mp_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_path(repo_root: Path, material_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", material_id.strip())[:120] or "unknown"
    return mp_cache_dir(repo_root) / f"{safe}.json"


def load_cache(repo_root: Path, material_id: str) -> dict[str, Any] | None:
    path = cache_path(repo_root, material_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def save_cache(repo_root: Path, material_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    path = cache_path(repo_root, material_id)
    payload = {
        **payload,
        "cache_version": _CACHE_VERSION,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "material_id": material_id,
    }
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)
    return payload


def mp_api_key_configured() -> bool:
    return bool(str(os.getenv("MP_API_KEY") or "").strip())


def _local_capabilities(material: dict[str, Any], structure: dict[str, Any] | None, details: dict[str, Any] | None) -> dict[str, bool]:
    has_props = {str(item).lower() for item in (material.get("has_props") or []) if item}
    spectra_count = int(((details or {}).get("details") or {}).get("spectra", {}).get("count") or 0)
    sites = (structure or {}).get("sites") or []
    description = str(material.get("description") or "").strip()
    return {
        "structure": bool(sites) or bool((structure or {}).get("has_full_structure")),
        # Only claim spectra when local records exist; has_props alone can be stale.
        # Live MP enrich will flip this true when XAS docs are actually returned.
        "spectra": spectra_count > 0,
        "thermo": "thermo" in has_props or material.get("energy_above_hull") is not None,
        "electronic": "electronic_structure" in has_props or "bandstructure" in has_props or material.get("band_gap") is not None,
        "magnetic": "magnetism" in has_props or material.get("ordering") is not None,
        "mechanical": "elasticity" in has_props or material.get("bulk_modulus_vrh") is not None,
        "dielectric": "dielectric" in has_props,
        "summary": bool(description),
        "bonds": "chemenv" in has_props or "oxi_states" in has_props,
        "surface": "substrates" in has_props,
    }


def _resolve_mp_material_id(material: dict[str, Any]) -> str | None:
    mid = str(material.get("resolved_material_id") or material.get("material_id") or "").strip()
    if _MP_ID_RE.match(mid):
        return mid.lower()
    for key in ("mp_id", "task_id"):
        value = str(material.get(key) or "").strip()
        if _MP_ID_RE.match(value):
            return value.lower()
    dbids = material.get("database_ids") or {}
    if isinstance(dbids, dict):
        for key in ("mp", "materials_project", "mp_id"):
            value = dbids.get(key)
            if isinstance(value, list) and value:
                candidate = str(value[0]).strip()
                if _MP_ID_RE.match(candidate):
                    return candidate.lower()
            if isinstance(value, str) and _MP_ID_RE.match(value.strip()):
                return value.strip().lower()
    return None


MP_API_BASE = "https://api.materialsproject.org"


def _mp_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Single HTTP GET against Materials Project REST (no mp-api client required)."""
    import urllib.error
    import urllib.parse
    import urllib.request

    key = str(os.getenv("MP_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("MP_API_KEY is not set")
    query = urllib.parse.urlencode(params or {}, doseq=True)
    url = f"{MP_API_BASE}{path}"
    if query:
        url = f"{url}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "X-API-KEY": key,
            "Accept": "application/json",
            "User-Agent": "Catalyst/0.1 (selected-material enrich)",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1500]
        raise RuntimeError(f"MP HTTP {exc.code}: {detail}") from exc


def _structure_from_mp_dict(raw: dict[str, Any], material_id: str, formula: str | None) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    lattice_raw = raw.get("lattice") or {}
    matrix = lattice_raw.get("matrix")
    sites_out: list[dict[str, Any]] = []
    for idx, site in enumerate(raw.get("sites") or []):
        if not isinstance(site, dict):
            continue
        species = site.get("species") or []
        element = None
        if isinstance(species, list) and species:
            first = species[0]
            if isinstance(first, dict):
                element = first.get("element")
            elif isinstance(first, str):
                element = first
        element = element or site.get("label")
        sites_out.append(
            {
                "index": idx,
                "label": site.get("label") or element or f"site_{idx}",
                "element": element,
                "abc": to_jsonable(site.get("abc") or []),
                "xyz": to_jsonable(site.get("xyz") or []),
                "species": to_jsonable(species),
            }
        )
    if not sites_out:
        return None
    lattice = {
        "a": lattice_raw.get("a"),
        "b": lattice_raw.get("b"),
        "c": lattice_raw.get("c"),
        "alpha": lattice_raw.get("alpha"),
        "beta": lattice_raw.get("beta"),
        "gamma": lattice_raw.get("gamma"),
        "volume": lattice_raw.get("volume"),
        "matrix": to_jsonable(matrix) if matrix is not None else None,
        "pbc": lattice_raw.get("pbc") or [True, True, True],
    }
    return {
        "material_id": material_id,
        "resolved_material_id": material_id,
        "formula_pretty": formula,
        "lattice": lattice,
        "sites": sites_out,
        "nsites": len(sites_out),
        "has_full_structure": True,
        "source": "materials_project_api",
        "message": None,
        "symmetry": to_jsonable(raw.get("symmetry")) if raw.get("symmetry") else None,
    }


def _fetch_from_mp(material: dict[str, Any]) -> dict[str, Any]:
    """Live MP pull for exactly one material via REST. Requires MP_API_KEY."""
    local_id = str(material.get("material_id") or "")
    formula = material.get("formula_pretty")
    mp_id = _resolve_mp_material_id(material)
    started = time.time()
    summary_doc: dict[str, Any] = {}
    description = str(material.get("description") or "").strip() or None
    structure_payload = None
    spectra_records: list[dict[str, Any]] = []
    resolved_via = "none"
    errors: list[str] = []

    # Resolve canonical MP id if local id is catalyst-style (mp-zw, etc.)
    if not mp_id and formula:
        try:
            # Prefer experimentally-stable / low-hull polymorph for formula matches.
            payload = _mp_get(
                "/materials/summary/",
                {
                    "formula": str(formula),
                    "is_stable": "true",
                    "_limit": 8,
                    "_fields": "material_id,formula_pretty,energy_above_hull,is_stable,has_props",
                },
            )
            hits = payload.get("data") or []
            if not hits:
                payload = _mp_get(
                    "/materials/summary/",
                    {
                        "formula": str(formula),
                        "_limit": 8,
                        "_fields": "material_id,formula_pretty,energy_above_hull,is_stable,has_props",
                    },
                )
                hits = payload.get("data") or []
            if hits:
                hits_sorted = sorted(
                    hits,
                    key=lambda row: (
                        0 if row.get("is_stable") else 1,
                        float(row.get("energy_above_hull") if row.get("energy_above_hull") is not None else 99),
                    ),
                )
                mp_id = str(hits_sorted[0].get("material_id") or "").strip() or None
                resolved_via = "formula_search"
        except Exception as exc:
            errors.append(f"formula_search: {exc}")
            mp_id = None

    if mp_id and not resolved_via.startswith("formula"):
        resolved_via = "direct_id"

    if mp_id:
        try:
            payload = _mp_get(
                "/materials/summary/",
                {
                    "material_ids": mp_id,
                    "_limit": 1,
                    "_fields": (
                        "material_id,formula_pretty,band_gap,formation_energy_per_atom,"
                        "energy_above_hull,is_stable,is_metal,is_magnetic,ordering,density,"
                        "volume,symmetry,description,has_props"
                    ),
                },
            )
            docs = payload.get("data") or []
            if docs:
                summary_doc = to_jsonable(docs[0])
                if summary_doc.get("description"):
                    description = str(summary_doc.get("description")).strip() or description
        except Exception as exc:
            errors.append(f"summary: {exc}")

        if not description:
            try:
                payload = _mp_get(
                    "/materials/robocrys/",
                    {
                        "material_ids": mp_id,
                        "_limit": 1,
                        "_fields": "material_id,description",
                    },
                )
                robos = payload.get("data") or []
                if robos and robos[0].get("description"):
                    description = str(robos[0]["description"]).strip()
                    resolved_via = f"{resolved_via}+robocrys"
            except Exception as exc:
                errors.append(f"robocrys: {exc}")

        try:
            payload = _mp_get(
                "/materials/core/",
                {
                    "material_ids": mp_id,
                    "_limit": 1,
                    "_fields": "material_id,formula_pretty,structure,symmetry",
                },
            )
            cores = payload.get("data") or []
            if cores:
                core = cores[0]
                structure_payload = _structure_from_mp_dict(
                    core.get("structure") or {},
                    mp_id,
                    formula or core.get("formula_pretty") or summary_doc.get("formula_pretty"),
                )
                if structure_payload and core.get("symmetry") and not structure_payload.get("symmetry"):
                    structure_payload["symmetry"] = to_jsonable(core.get("symmetry"))
        except Exception as exc:
            errors.append(f"structure: {exc}")

        # XAS endpoint is flaky with material_ids on some MP versions; try id then formula.
        xas_fields = "material_id,spectrum,absorbing_element,edge,spectrum_type,spectrum_id"
        xas_params_list: list[dict[str, Any]] = [
            {"material_ids": mp_id, "_limit": 8, "_fields": xas_fields},
        ]
        if formula:
            xas_params_list.append({"formula": str(formula), "_limit": 8, "_fields": xas_fields})
        for params in xas_params_list:
            try:
                payload = _mp_get("/materials/xas/", params)
                docs = payload.get("data") or []
                if not docs:
                    continue
                for doc in docs[:8]:
                    row = to_jsonable(doc)
                    doc_mid = str(row.get("material_id") or "")
                    spectrum = row.get("spectrum") if isinstance(row, dict) else None
                    if isinstance(spectrum, dict):
                        x = spectrum.get("x") or spectrum.get("energy")
                        y = spectrum.get("y") or spectrum.get("intensity")
                        if isinstance(x, list) and isinstance(y, list) and len(x) > 240:
                            step = max(1, len(x) // 240)
                            spectrum["x"] = x[::step][:240]
                            spectrum["y"] = y[::step][:240]
                        row["spectrum"] = spectrum
                    elif not spectrum:
                        continue
                    row["material_id"] = local_id
                    row["mp_material_id"] = doc_mid or mp_id
                    spectra_records.append(row)
                if spectra_records:
                    break
            except Exception as exc:
                errors.append(f"xas({list(params.keys())}): {exc}")

    caps = {
        "structure": bool(structure_payload and structure_payload.get("sites")),
        "spectra": bool(spectra_records),
        "summary": bool(description),
        "thermo": summary_doc.get("energy_above_hull") is not None
        or summary_doc.get("formation_energy_per_atom") is not None,
        "electronic": summary_doc.get("band_gap") is not None,
        "magnetic": summary_doc.get("ordering") is not None or summary_doc.get("is_magnetic") is not None,
        "mechanical": False,
        "dielectric": False,
        "bonds": False,
        "surface": False,
    }
    return {
        "ok": True,
        "source": "materials_project_api" if mp_id else "local_only",
        "mp_material_id": mp_id,
        "resolved_via": resolved_via,
        "description": description,
        "summary": summary_doc,
        "structure": structure_payload,
        "spectra": {
            "records": spectra_records,
            "count": len(spectra_records),
            "source": "materials_project_api" if spectra_records else "none",
        },
        "capabilities": caps,
        "elapsed_ms": int((time.time() - started) * 1000),
        "mp_configured": True,
        "mp_errors": errors or None,
    }


def enrich_material(
    store: Any,
    repo_root: Path,
    material_id: str,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Enrich exactly one selected material. Uses disk cache; optional live MP."""
    material = store.get_material(material_id)
    if not material:
        return {"ok": False, "error": f"Material not found: {material_id}", "material_id": material_id}

    mid = str(material.get("material_id") or material_id)
    if not force:
        cached = load_cache(repo_root, mid)
        if cached and cached.get("ok"):
            cached["cache_hit"] = True
            return cached

    structure = store.structure(mid)
    try:
        details = store.material_details(mid, sections=["spectra", "thermo", "electronic_structure"], limit=8, downsample=True)
    except Exception:
        details = None

    local_caps = _local_capabilities(material, structure, details)
    description = str(material.get("description") or "").strip() or None

    base: dict[str, Any] = {
        "ok": True,
        "material_id": mid,
        "formula_pretty": material.get("formula_pretty"),
        "cache_hit": False,
        "mp_configured": mp_api_key_configured(),
        "source": "local_snapshot",
        "description": description,
        "summary": {},
        "structure": structure if structure and structure.get("has_full_structure") else None,
        "spectra": {
            "records": ((details or {}).get("details") or {}).get("spectra", {}).get("records") or [],
            "count": int(((details or {}).get("details") or {}).get("spectra", {}).get("count") or 0),
            "source": "local_snapshot",
        },
        "capabilities": local_caps,
        "mp_material_id": _resolve_mp_material_id(material),
        "resolved_via": "local",
        "elapsed_ms": 0,
    }

    # Prefer local structure/spectra when present; only hit MP for gaps or force.
    needs_mp = force or not description or not local_caps.get("structure") or not local_caps.get("spectra")
    if needs_mp and mp_api_key_configured():
        try:
            remote = _fetch_from_mp(material)
            # Merge: keep local structure if good; fill gaps from MP
            if remote.get("description"):
                base["description"] = remote["description"]
            if remote.get("summary"):
                base["summary"] = remote["summary"]
            if remote.get("mp_material_id"):
                base["mp_material_id"] = remote["mp_material_id"]
            if remote.get("resolved_via"):
                base["resolved_via"] = remote["resolved_via"]
            if remote.get("structure") and (force or not base.get("structure") or not (base.get("structure") or {}).get("sites")):
                base["structure"] = remote["structure"]
            remote_spectra = (remote.get("spectra") or {}).get("records") or []
            if remote_spectra and (force or not base["spectra"]["count"]):
                base["spectra"] = remote["spectra"]
            # capabilities OR of local + remote
            merged_caps = dict(local_caps)
            for key, value in (remote.get("capabilities") or {}).items():
                merged_caps[key] = bool(merged_caps.get(key) or value)
            if base.get("description"):
                merged_caps["summary"] = True
            if base.get("structure") and (base["structure"] or {}).get("sites"):
                merged_caps["structure"] = True
            if base["spectra"]["count"]:
                merged_caps["spectra"] = True
            base["capabilities"] = merged_caps
            base["source"] = remote.get("source") or "materials_project_api"
            base["elapsed_ms"] = remote.get("elapsed_ms") or 0
            base["mp_error"] = None
        except Exception as exc:
            base["mp_error"] = f"{type(exc).__name__}: {exc}"
            base["source"] = "local_snapshot"
    elif needs_mp and not mp_api_key_configured():
        base["mp_error"] = "MP_API_KEY not configured on server"
        base["mp_configured"] = False

    return save_cache(repo_root, mid, base)


def get_enrichment(repo_root: Path, material_id: str) -> dict[str, Any] | None:
    return load_cache(repo_root, material_id)
