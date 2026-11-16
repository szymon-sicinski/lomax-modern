"""Keeps ``src/`` importable without an install and provides the repo root."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (str(ROOT), str(SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)

#: Test package needs to be importable as ``tests.fixtures.synth``.
(ROOT / "tests" / "__init__.py").touch(exist_ok=True)
