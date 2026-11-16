#!/usr/bin/env python3
"""Measure a Lomax installation and print the numbers, read-only.

    scripts/measure_worlds.py /path/to/Lomax
    scripts/measure_worlds.py /path/to/Lomax --json report.json
    scripts/measure_worlds.py /path/to/Lomax --quiet > /tmp/report.json

Nothing is written to the game folder. See src/lomax_modern/measure.py for what
each probe does and how unverified layouts are labelled.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lomax_modern.measure import measure_install, summarise, to_json  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game_dir", help="folder containing LOMAX.EXE")
    parser.add_argument("--json", metavar="PATH", help="also write the raw report here")
    parser.add_argument("--quiet", action="store_true", help="print JSON instead of the digest")
    args = parser.parse_args(argv)

    root = Path(args.game_dir)
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    report = measure_install(root)
    if args.json:
        Path(args.json).write_text(to_json(report), encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)

    print(to_json(report) if args.quiet else summarise(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
