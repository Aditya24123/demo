#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/catalyst-live"
. .venv/bin/activate
export PYTHONPATH="$HOME/catalyst-live/code/backend/pipeline"
export CATALYST_REPO_ROOT="$HOME/catalyst-live"
export CATALYST_API_PORT="8766"
if [ -f "$HOME/catalyst-live/.secrets/gemini_api_key" ]; then
  export GEMINI_API_KEY="$(cat "$HOME/catalyst-live/.secrets/gemini_api_key")"
fi
if [ -f "$HOME/catalyst-live/.secrets/micro_api_key" ]; then
  export MICRO_API_KEY="$(cat "$HOME/catalyst-live/.secrets/micro_api_key")"
fi
if [ -f "$HOME/catalyst-live/.secrets/mp_api_key" ]; then
  export MP_API_KEY="$(cat "$HOME/catalyst-live/.secrets/mp_api_key")"
fi
exec uvicorn catalyst.local_api:app --host 127.0.0.1 --port 8766
