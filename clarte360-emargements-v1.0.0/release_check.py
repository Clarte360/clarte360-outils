#!/usr/bin/env python3
"""Contrôle local de candidate avant commit/push.

Ne modifie ni la base ni le VPS. Lance compilation, imports et pytest.
"""
from __future__ import annotations

import compileall
import importlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODULES = ["db", "security", "pdf_utils", "services", "mailer", "graph_client", "pip_connector", "ui_guard", "production_readiness"]


def main() -> int:
    print("[1/3] Compilation Python")
    if not compileall.compile_dir(str(ROOT), quiet=1, rx=__import__('re').compile(r"[\\/]\.venv[\\/]")):
        print("ECHEC compilation")
        return 1

    print("[2/3] Imports principaux")
    sys.path.insert(0, str(ROOT))
    for name in MODULES:
        importlib.import_module(name)
        print(f"  OK {name}")

    print("[3/3] Pytest")
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)
    if proc.returncode:
        return proc.returncode
    print("CANDIDATE TECHNIQUE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
