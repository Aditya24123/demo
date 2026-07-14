#!/usr/bin/env python3
"""Restart Catalyst API on mini host."""
from __future__ import annotations

import os
import signal
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path.home() / "catalyst-live"


def main() -> int:
    out = subprocess.check_output(["ps", "-eo", "pid,cmd"], text=True)
    for line in out.splitlines():
        if ".venv/bin/uvicorn" in line and "catalyst.local_api" in line:
            try:
                os.kill(int(line.split(None, 1)[0]), signal.SIGTERM)
            except ProcessLookupError:
                pass
    time.sleep(2)
    subprocess.Popen(
        ["bash", str(ROOT / "start-catalyst-live.sh")],
        cwd=str(ROOT),
        stdout=open("/tmp/catalyst-live-restart.log", "a", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    for _ in range(20):
        try:
            print(urllib.request.urlopen("http://127.0.0.1:8766/health", timeout=2).read().decode())
            return 0
        except Exception:
            time.sleep(1)
    print("down")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
