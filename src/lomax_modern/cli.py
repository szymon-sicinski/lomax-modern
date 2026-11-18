"""Command line interface for the Lomax research toolkit."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .doctor import find_world_files, format_report, inventory
from .measure import measure_install, summarise, to_json
from .wld import WLDError, parse_file
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


def _cmd_wld_roundtrip(args: argparse.Namespace) -> int:
    """Re-parse every world file and compare the re-emit byte-for-byte.

    Read-only: nothing is written anywhere. Each file is parsed, re-serialised
    in memory with :func:`lomax_modern.wld.World.to_bytes`, and the two byte
    strings are compared directly. The verdict prints the file name only --
    never payload bytes and never a file digest.
    """
    if args.wld_file:
        files = [Path(args.wld_file)]
        if not files[0].is_file():
            print(f"error: not a file: {files[0]}", file=sys.stderr)
            return 2
    else:
        game_dir = args.game_dir or os.environ.get("LOMAX_GAME_DIR")
        if not game_dir:
            print(
                "error: pass a WLD file, or set LOMAX_GAME_DIR (or --game-dir) "
                "to a Lomax installation",
                file=sys.stderr,
            )
            return 2
        files = find_world_files(game_dir)
        if not files:
            print(f"error: no *.WLD found under {game_dir}", file=sys.stderr)
            return 2

    any_diff = False
    for path in files:
        try:
            source = path.read_bytes()
            world = parse_file(path)
            rebuilt = world.to_bytes()
        except (OSError, WLDError) as exc:
            print(f"{path.name}: ERROR ({exc})", file=sys.stderr)
            any_diff = True
            continue
        ok = rebuilt == source
        any_diff = any_diff or not ok
        verdict = "identical" if ok else "DIFFERENT"
        print(f"{path.name}: {verdict} ({len(world)} chunks, {len(source)} bytes)")

    return 1 if (args.check and any_diff) else 0


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

    p_wld = sub.add_parser("wld", help="read and re-emit .WLD world containers (read-only)")
    wld_sub = p_wld.add_subparsers(dest="wld_command", required=True)

    p_rt = wld_sub.add_parser(
        "roundtrip",
        help="parse and re-serialise world files, reporting byte-identical round trips",
    )
    p_rt.add_argument(
        "wld_file",
        nargs="?",
        default=None,
        help="single .WLD file (default: every WORLDS/*.WLD under LOMAX_GAME_DIR)",
    )
    p_rt.add_argument(
        "--game-dir",
        default=None,
        help="folder containing WORLDS/*.WLD (default: $LOMAX_GAME_DIR)",
    )
    p_rt.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if any file does not round-trip byte-exactly",
    )
    p_rt.set_defaults(func=_cmd_wld_roundtrip)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
