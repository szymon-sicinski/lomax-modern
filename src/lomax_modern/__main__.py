"""``python -m lomax_modern`` entry point (same CLI as the console script)."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
