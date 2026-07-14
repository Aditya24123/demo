#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/catalyst-live"
. .venv/bin/activate
python --version
# mini runs Python 3.10; mp-api>=0.46 needs 3.11+. Pin a 3.10-compatible release.
pip install "mp-api==0.45.15" "pymatgen>=2024.1.0"
python - <<'PY'
from mp_api.client import MPRester
import os
print("mp_api_ok")
key = os.environ.get("MP_API_KEY") or open(os.path.expanduser("~/catalyst-live/.secrets/mp_api_key")).read().strip()
with MPRester(key, mute_progress_bars=True, use_document_model=False) as mpr:
    docs = list(mpr.materials.summary.search(material_ids=["mp-1497"], fields=["material_id", "formula_pretty"], num_chunks=1, chunk_size=1))
    print("sample", docs[0] if docs else None)
PY
