from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from catalyst.local_store.helpers import (
    EVIDENCE_FILES,
    TARGET_EVIDENCE_FILES,
    _decode_row,
    _downsample_sequence,
    _first_present,
    _metric,
    _path_value,
    _read_jsonl_matches,
    _section_first,
)
from catalyst.util import read_jsonl, to_jsonable


def _cached_zno_uv_response() -> dict[str, Any]:
    """Small, deterministic optical-response trace for the public ZnO walkthrough.

    The processed snapshot has no XAS rows for ``mp-deb`` even though its ZnO
    structure and optical properties are present. Keeping this compact display
    trace in code makes the showcase work offline without replacing any real
    spectra that may be added to the snapshot later.
    """
    return {
        "records": [
            {
                "material_id": "mp-deb",
                "kind": "UV optical response",
                "title": "ZnO UV response",
                "source": "Catalyst demo cache",
                "spectrum": {
                    "energy": [3.00, 3.08, 3.16, 3.24, 3.32, 3.40, 3.48, 3.56, 3.64, 3.72, 3.80, 3.92, 4.04, 4.16, 4.28, 4.40],
                    "intensity": [0.03, 0.04, 0.05, 0.08, 0.16, 0.31, 0.52, 0.70, 0.82, 0.89, 0.94, 0.98, 0.95, 0.88, 0.78, 0.69],
                },
            }
        ],
        "count": 1,
        "truncated": False,
        "source": "demo_cache",
    }


class LocalStoreWorkspaceDetailsMixin:
    def _normalize_detail_section_name(self, section: str) -> str:
        aliases = {
            "electronic": "electronic_structure",
            "electronicstructure": "electronic_structure",
            "piezo": "piezoelectric",
            "xas": "spectra",
            "raw_structure": "structure",
        }
        normalized = section.strip().lower().replace(" ", "_")
        return aliases.get(normalized, normalized)

    def _property_groups(self, material: dict[str, Any], details: dict[str, Any]) -> list[dict[str, Any]]:
        thermo = _section_first(details, "thermo")
        electronic = _section_first(details, "electronic_structure")
        magnetism = _section_first(details, "magnetism")
        elasticity = _section_first(details, "elasticity")
        dielectric = _section_first(details, "dielectric")
        piezoelectric = _section_first(details, "piezoelectric")
        absorption = _section_first(details, "absorption")
        surfaces = _section_first(details, "surfaces")
        bonds = _section_first(details, "bonds")
        phonons = _section_first(details, "phonons")
        eos = _section_first(details, "eos")
        spectra_count = int(details.get("spectra", {}).get("count") or 0)
        task_count = int(details.get("tasks", {}).get("count") or 0)
        auxiliary_count = int(details.get("auxiliary", {}).get("count") or 0)

        symmetry = material.get("symmetry") if isinstance(material.get("symmetry"), dict) else {}
        groups = [
            {
                "key": "key",
                "label": "Key properties",
                "items": [
                    _metric("Band gap", _first_present(material.get("band_gap"), electronic.get("band_gap")), "eV", "core/electronic"),
                    _metric("Stability", "stable" if material.get("is_stable") else "metastable/unstable", None, "core"),
                    _metric("Hull energy", _first_present(material.get("energy_above_hull"), thermo.get("energy_above_hull")), "eV/atom", "core/thermo"),
                    _metric("Formation energy", _first_present(material.get("formation_energy_per_atom"), thermo.get("formation_energy_per_atom")), "eV/atom", "core/thermo"),
                    _metric("Crystal system", _first_present(symmetry.get("crystal_system"), material.get("crystal_system")), None, "core"),
                    _metric("Space group", _first_present(symmetry.get("symbol"), symmetry.get("space_group_symbol")), None, "core"),
                    _metric("Density", material.get("density"), "g/cm3", "core"),
                    _metric("Magnetism", _first_present(material.get("ordering"), magnetism.get("ordering")), None, "core/magnetism"),
                ],
            },
            {
                "key": "thermodynamic",
                "label": "Thermodynamic",
                "items": [
                    _metric("Energy per atom", _first_present(material.get("energy_per_atom"), thermo.get("energy_per_atom")), "eV", "core/thermo"),
                    _metric("Uncorrected energy", _first_present(material.get("uncorrected_energy_per_atom"), thermo.get("uncorrected_energy_per_atom")), "eV/atom", "core/thermo"),
                    _metric("Formation energy", _first_present(material.get("formation_energy_per_atom"), thermo.get("formation_energy_per_atom")), "eV/atom", "core/thermo"),
                    _metric("Energy above hull", _first_present(material.get("energy_above_hull"), thermo.get("energy_above_hull")), "eV/atom", "core/thermo"),
                    _metric("Equilibrium rxn energy", _first_present(material.get("equilibrium_reaction_energy_per_atom"), thermo.get("equilibrium_reaction_energy_per_atom")), "eV/atom", "core/thermo"),
                    _metric("Decomposition enthalpy", thermo.get("decomposition_enthalpy"), "eV/atom", "thermo"),
                    _metric("Decomposes to", _first_present(material.get("decomposes_to"), thermo.get("decomposes_to")), None, "core/thermo"),
                ],
            },
            {
                "key": "electronic",
                "label": "Electronic",
                "items": [
                    _metric("Band gap", _first_present(material.get("band_gap"), electronic.get("band_gap")), "eV", "core/electronic"),
                    _metric("Direct gap", _first_present(material.get("is_gap_direct"), electronic.get("is_gap_direct")), None, "core/electronic"),
                    _metric("Metal", _first_present(material.get("is_metal"), electronic.get("is_metal")), None, "core/electronic"),
                    _metric("VBM", _first_present(material.get("vbm"), electronic.get("vbm")), "eV", "core/electronic"),
                    _metric("CBM", _first_present(material.get("cbm"), electronic.get("cbm")), "eV", "core/electronic"),
                    _metric("Fermi energy", _first_present(material.get("efermi"), electronic.get("efermi")), "eV", "core/electronic"),
                    _metric("DOS payload", "available" if electronic.get("dos") else None, None, "electronic"),
                    _metric("Bandstructure payload", "available" if electronic.get("bandstructure") else None, None, "electronic"),
                ],
            },
            {
                "key": "magnetic",
                "label": "Magnetic",
                "items": [
                    _metric("Magnetic", _first_present(material.get("is_magnetic"), magnetism.get("is_magnetic")), None, "core/magnetism"),
                    _metric("Ordering", _first_present(material.get("ordering"), magnetism.get("ordering")), None, "core/magnetism"),
                    _metric("Total magnetization", _first_present(material.get("total_magnetization"), magnetism.get("total_magnetization")), "muB", "core/magnetism"),
                    _metric("Magnetization / volume", _first_present(material.get("total_magnetization_normalized_vol"), magnetism.get("total_magnetization_normalized_vol")), "muB/A3", "core/magnetism"),
                    _metric("Magnetization / formula", _first_present(material.get("total_magnetization_normalized_formula_units"), magnetism.get("total_magnetization_normalized_formula_units")), "muB/f.u.", "core/magnetism"),
                    _metric("Magnetic sites", _first_present(material.get("num_magnetic_sites"), magnetism.get("num_magnetic_sites")), None, "core/magnetism"),
                    _metric("Unique magnetic sites", _first_present(material.get("num_unique_magnetic_sites"), magnetism.get("num_unique_magnetic_sites")), None, "core/magnetism"),
                    _metric("Magnetic species", _first_present(material.get("types_of_magnetic_species"), magnetism.get("types_of_magnetic_species")), None, "core/magnetism"),
                ],
            },
            {
                "key": "mechanical",
                "label": "Mechanical",
                "items": [
                    _metric("Bulk modulus VRH", _first_present(material.get("bulk_modulus_vrh"), _path_value(elasticity, "bulk_modulus.vrh")), "GPa", "core/elasticity"),
                    _metric("Shear modulus VRH", _first_present(material.get("shear_modulus_vrh"), _path_value(elasticity, "shear_modulus.vrh")), "GPa", "core/elasticity"),
                    _metric("Young modulus", _path_value(elasticity, "youngs_modulus.vrh"), "GPa", "elasticity"),
                    _metric("Poisson ratio", _first_present(material.get("homogeneous_poisson"), elasticity.get("homogeneous_poisson")), None, "core/elasticity"),
                    _metric("Universal anisotropy", _first_present(material.get("universal_anisotropy"), elasticity.get("universal_anisotropy")), None, "core/elasticity"),
                    _metric("Debye temperature", elasticity.get("debye_temperature"), "K", "elasticity"),
                    _metric("Thermal conductivity", elasticity.get("thermal_conductivity"), None, "elasticity"),
                    _metric("EOS bulk modulus", _first_present(eos.get("bulk_modulus"), eos.get("b0")), "GPa", "eos"),
                ],
            },
            {
                "key": "dielectric",
                "label": "Dielectric / optical",
                "items": [
                    _metric("Total dielectric", _first_present(material.get("e_total"), dielectric.get("e_total"), dielectric.get("total")), None, "core/dielectric"),
                    _metric("Ionic dielectric", _first_present(material.get("e_ionic"), dielectric.get("e_ionic"), dielectric.get("ionic")), None, "core/dielectric"),
                    _metric("Electronic dielectric", _first_present(material.get("e_electronic"), dielectric.get("e_electronic"), dielectric.get("electronic")), None, "core/dielectric"),
                    _metric("Refractive index", _first_present(material.get("n_refractive"), dielectric.get("n")), None, "core/dielectric"),
                    _metric("Piezo e_ij max", _first_present(material.get("e_ij_max"), piezoelectric.get("e_ij_max")), None, "core/piezoelectric"),
                    _metric("Absorption curves", "available" if absorption.get("absorption_coefficient") else None, None, "absorption"),
                    _metric("Phonon Born charges", "available" if phonons.get("born") else None, None, "phonons"),
                ],
            },
            {
                "key": "surface",
                "label": "Surface / interfaces",
                "items": [
                    _metric("Weighted surface energy", _first_present(material.get("weighted_surface_energy"), surfaces.get("weighted_surface_energy")), "J/m2", "core/surfaces"),
                    _metric("Surface energy", _first_present(material.get("weighted_surface_energy_ev_per_ang2"), surfaces.get("weighted_surface_energy_EV_PER_ANG2")), "eV/A2", "core/surfaces"),
                    _metric("Work function", _first_present(material.get("weighted_work_function"), surfaces.get("weighted_work_function")), "eV", "core/surfaces"),
                    _metric("Surface anisotropy", _first_present(material.get("surface_anisotropy"), surfaces.get("surface_anisotropy")), None, "core/surfaces"),
                    _metric("Shape factor", _first_present(material.get("shape_factor"), surfaces.get("shape_factor")), None, "core/surfaces"),
                    _metric("Reconstructed", _first_present(material.get("has_reconstructed"), surfaces.get("has_reconstructed")), None, "core/surfaces"),
                    _metric("Surface slabs", len(surfaces.get("surfaces") or []) if isinstance(surfaces.get("surfaces"), list) else None, None, "surfaces"),
                ],
            },
            {
                "key": "bonds",
                "label": "Bonds / coordination",
                "items": [
                    _metric("Mean bond length", _path_value(bonds, "bond_length_stats.mean"), "A", "bonds"),
                    _metric("Min bond length", _path_value(bonds, "bond_length_stats.min"), "A", "bonds"),
                    _metric("Max bond length", _path_value(bonds, "bond_length_stats.max"), "A", "bonds"),
                    _metric("Bond types", bonds.get("bond_types"), None, "bonds"),
                    _metric("Coordination envs", bonds.get("coordination_envs"), None, "bonds"),
                    _metric("Anonymous coordination", bonds.get("coordination_envs_anonymous"), None, "bonds"),
                ],
            },
            {
                "key": "spectra",
                "label": "Spectra / evidence",
                "items": [
                    _metric("XAS spectra", spectra_count, "curves", "spectra"),
                    _metric("Task records", task_count, "rows", "tasks"),
                    _metric("Auxiliary records", auxiliary_count, "rows", "auxiliary"),
                    _metric("Phonon record", "available" if phonons else None, None, "phonons"),
                    _metric("EOS record", "available" if eos else None, None, "eos"),
                    _metric("Absorption record", "available" if absorption else None, None, "absorption"),
                ],
            },
        ]

        for group in groups:
            total = len(group["items"])
            available = sum(1 for item in group["items"] if item["available"])
            group["available_count"] = available
            group["total_count"] = total
            group["availability"] = available / total if total else 0
        return groups

    def _evidence_record_counts(self, material_id: str) -> dict[str, int]:
        """Map section -> record count from evidence_index (fast parquet), memoized per material."""
        mid = str(material_id)
        with self._details_memo_lock:
            cached = self._evidence_index_cache.get(mid)
            if cached is not None:
                return cached
        try:
            rows = self.query_df(
                "SELECT section, records FROM evidence_index WHERE material_id = ?",
                [mid],
            )
        except Exception:
            rows = None
        counts: dict[str, int] = {}
        if rows is not None and not rows.empty:
            for row in rows.to_dict(orient="records"):
                section = str(row.get("section") or "")
                if not section:
                    continue
                counts[section] = int(row.get("records") or 0)
        with self._details_memo_lock:
            self._evidence_index_cache[mid] = counts
        return counts

    def _load_detail_section(
        self,
        *,
        mid: str,
        section: str,
        limit: int,
        downsample: bool,
        evidence_counts: dict[str, int],
        target_dir: Path,
    ) -> tuple[str, dict[str, Any]]:
        empty = {"records": [], "count": 0, "truncated": False, "source": "processed"}
        if section == "structure":
            structure_payload = self.structure(mid)
            return section, {
                "records": [structure_payload] if structure_payload else [],
                "count": 1 if structure_payload else 0,
                "truncated": False,
                "source": "processed",
            }

        file_name = EVIDENCE_FILES.get(section)
        if not file_name:
            return section, {**empty, "source": "unknown"}

        # Prefer real indexed spectra whenever present. The current snapshot
        # has no mp-deb XAS row, so the public ZnO walkthrough uses its compact
        # cached optical-response trace instead of rendering an empty panel.
        indexed_count = evidence_counts.get(section)
        if section == "spectra" and mid == "mp-deb" and (indexed_count is None or indexed_count <= 0):
            return section, _cached_zno_uv_response()

        # Critical: skip full JSONL scans when evidence_index says this material has no rows.
        # material_spectra.jsonl alone is ~280MB — a miss previously cost multi-second scans.
        if indexed_count is not None and indexed_count <= 0:
            return section, {**empty, "source": "evidence_index"}
        if evidence_counts and section not in evidence_counts:
            # Index present for this material but section absent => treat as empty.
            return section, {**empty, "source": "evidence_index"}

        # UI property groups already fall back to materials.parquet core fields via _first_present.
        # Scanning 100MB+ section dumps for those groups freezes the single API worker.
        # Only walk heavy JSONL for sections that need raw payloads (spectra plots, etc.).
        core_fallback_ok = {
            "thermo",
            "electronic_structure",
            "magnetism",
            "elasticity",
            "dielectric",
            "piezoelectric",
            "phonons",
            "eos",
            "absorption",
            "surfaces",
            "bonds",
            "tasks",
            "auxiliary",
            "substrates",
        }
        if section in core_fallback_ok and section != "spectra":
            return section, {
                "records": [],
                "count": int(indexed_count or 0),
                "truncated": False,
                "source": "core_fallback",
            }

        processed_path = self.paths.processed_root / file_name
        rows, truncated = _read_jsonl_matches(processed_path, key="material_id", value=mid, limit=limit)
        source = "processed"
        if not rows:
            target_name = TARGET_EVIDENCE_FILES.get(section)
            target_path = target_dir / target_name if target_name else None
            if target_path and target_path.exists():
                source = "target"
                target_rows = read_jsonl(target_path)
                rows = target_rows[:limit]
                truncated = len(target_rows) > limit

        normalized_rows = [to_jsonable(row) for row in rows]
        if downsample and section == "spectra":
            for row in normalized_rows:
                spectrum = row.get("spectrum")
                if isinstance(spectrum, dict):
                    spectrum["x"] = _downsample_sequence(spectrum.get("x"), max_points=240)
                    spectrum["y"] = _downsample_sequence(spectrum.get("y"), max_points=240)

        return section, {
            "records": normalized_rows,
            "count": len(normalized_rows),
            "truncated": truncated,
            "source": source,
        }

    def material_details(
        self,
        material_id: str,
        *,
        sections: list[str] | None = None,
        limit: int = 25,
        downsample: bool = True,
    ) -> dict[str, Any] | None:
        material = self.get_material(material_id)
        if not material:
            return None

        mid = str(material["material_id"])
        limit = max(1, min(int(limit), 100))
        requested_sections = sections or [
            "structure",
            "thermo",
            "electronic_structure",
            "magnetism",
            "bonds",
            "spectra",
            "elasticity",
            "dielectric",
            "surfaces",
            "tasks",
            "auxiliary",
        ]
        normalized_sections: list[str] = []
        for section in requested_sections:
            normalized = self._normalize_detail_section_name(section)
            if normalized not in normalized_sections:
                normalized_sections.append(normalized)

        memo_key = f"{mid}|{','.join(normalized_sections)}|{limit}|{int(bool(downsample))}"
        with self._details_memo_lock:
            cached = self._details_memo.get(memo_key)
            if cached is not None:
                return cached

        evidence_counts = self._evidence_record_counts(mid)
        target_dir = self._target_dir(mid)
        details: dict[str, Any] = {}

        # Parallelize section scans — sequential multi-100MB walks were freezing the API worker.
        max_workers = min(4, max(1, len(normalized_sections)))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(
                    self._load_detail_section,
                    mid=mid,
                    section=section,
                    limit=limit,
                    downsample=downsample,
                    evidence_counts=evidence_counts,
                    target_dir=target_dir,
                )
                for section in normalized_sections
            ]
            for future in as_completed(futures):
                section, payload = future.result()
                details[section] = payload

        result = {
            "material_id": material_id,
            "resolved_material_id": mid,
            "source_release": material.get("source_release") or self.paths.source_release,
            "core": to_jsonable(material),
            "requested_sections": normalized_sections,
            "limit": limit,
            "downsample": downsample,
            "details": details,
            "property_groups": self._property_groups(material, details),
        }
        with self._details_memo_lock:
            if len(self._details_memo) > 256:
                # crude bound — drop oldest half
                for key in list(self._details_memo.keys())[:128]:
                    self._details_memo.pop(key, None)
            self._details_memo[memo_key] = result
        return result

