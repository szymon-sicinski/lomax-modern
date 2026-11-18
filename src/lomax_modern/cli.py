"""Command line interface for the Lomax research toolkit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .doctor import find_world_files, format_report, inventory
from .measure import measure_install, summarise, to_json
from .probe_anim_nmy import format_report as format_probe_report
from .probe_anim_nmy import probe_anim_nmy
from .wldscan import format_report as format_wld_report
from .wldscan import scan_file


def _cmd_doctor(args: argparse.Namespace) -> int:
    try:
        entries = inventory(args.game_dir)
    except NotADirectoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(format_report(entries, find_world_files(args.game_dir)))
    return 0


def _cmd_wldscan(args: argparse.Namespace) -> int:
    path = Path(args.wld_file)
    if not path.is_file():
        print(f"error: not a file: {path}", file=sys.stderr)
        return 2
    result = scan_file(path)
    print(format_wld_report(result))
    # Non-zero only on a hard failure, so CI can use this on fixtures.
    return 0 if result.chunks else 1


def _cmd_measure(args: argparse.Namespace) -> int:
    try:
        report = measure_install(args.game_dir)
    except NotADirectoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        Path(args.json).write_text(to_json(report), encoding="utf-8")
    print(to_json(report) if args.quiet else summarise(report))
    return 0


def _cmd_probe_anim_nmy(args: argparse.Namespace) -> int:
    if not Path(args.game_dir).is_dir():
        print(f"error: not a directory: {args.game_dir}", file=sys.stderr)
        return 2
    report = probe_anim_nmy(args.game_dir)
    if args.json:
        Path(args.json).write_text(to_json(report), encoding="utf-8")
    print(to_json(report) if args.quiet else format_probe_report(report))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lomax-modern",
        description=(
            "Research toolkit for The Adventures of Lomax (Psygnosis, 1996/97 PC). "
            "Read-only: it never modifies game files."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doc = sub.add_parser("doctor", help="inventory a game folder (read-only)")
    p_doc.add_argument("game_dir", help="folder containing LOMAX.EXE")
    p_doc.set_defaults(func=_cmd_doctor)

    p_scan = sub.add_parser("wldscan", help="list chunk tags and offsets of a .WLD file")
    p_scan.add_argument("wld_file", help="path to a WORLDS/*.WLD file")
    p_scan.set_defaults(func=_cmd_wldscan)

    p_meas = sub.add_parser(
        "measure",
        help="measure an install: chunk sequence, plane widths, audio formats (read-only)",
    )
    p_meas.add_argument("game_dir", help="folder containing LOMAX.EXE")
    p_meas.add_argument("--json", metavar="PATH", help="also write the raw report here")
    p_meas.add_argument("--quiet", action="store_true", help="print JSON instead of the digest")
    p_meas.set_defaults(func=_cmd_measure)

    p_probe = sub.add_parser(
        "probe-anim-nmy",
        help=(
            "structural probe for ANIM/NMY/GNMY chunks: offsets, token streams "
            "and record hypotheses scored by coverage (report, not parse)"
        ),
    )
    p_probe.add_argument("game_dir", help="folder containing LOMAX.EXE")
    p_probe.add_argument("--json", metavar="PATH", help="also write the raw report here")
    p_probe.add_argument("--quiet", action="store_true", help="print JSON instead of the digest")
    p_probe.set_defaults(func=_cmd_probe_anim_nmy)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
