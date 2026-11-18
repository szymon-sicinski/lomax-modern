"""Command line interface for the Lomax research toolkit."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from . import png
from .art import ArtError, export_world
from .anim_nmy import format_anim_nmy_report
from .anim_nmy import probe_anim_nmy as probe_recovered_framings
from .doctor import find_world_files, format_report, inventory
from .engine.render import frame_to_rgba
from .engine.run import run_slice
from .measure import measure_install, summarise, to_json
from .probe_anim_nmy import format_report as format_probe_report
from .probe_anim_nmy import probe_anim_nmy
from .wld import WLDError, parse_file
from .wldscan import format_report as format_wld_report
from .wldscan import scan_file


def _cmd_export(args: argparse.Namespace) -> int:
    source = Path(args.wld_file)
    if not source.is_file():
        print(f"error: not a file: {source}", file=sys.stderr)
        return 2
    try:
        report = export_world(
            source,
            args.out,
            palette_slot=args.palette,
            tile_layout=args.tile_layout,
            cell_columns=args.cell_columns,
            tile_columns=args.tile_columns,
            scale=args.scale,
            map_channel=args.map_field,
        )
    except (ArtError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(report.format())
    return 0


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


def _cmd_slice(args: argparse.Namespace) -> int:
    """Run the headless vertical slice of the first world (read-only)."""
    game_dir = args.game_dir or os.environ.get("LOMAX_GAME_DIR")
    if not game_dir:
        print(
            "error: pass GAME_DIR or set LOMAX_GAME_DIR to a Lomax installation",
            file=sys.stderr,
        )
        return 2
    if not Path(game_dir).is_dir():
        print(f"error: not a directory: {game_dir}", file=sys.stderr)
        return 2
    if args.frame:
        out = Path(args.frame).resolve()
        root = Path(game_dir).resolve()
        if out == root or root in out.parents:
            print(
                "error: --frame must not be written inside the game folder",
                file=sys.stderr,
            )
            return 2
    try:
        report, frame = run_slice(
            game_dir,
            worlds=(args.world,),
            max_ticks=args.ticks,
            playfield=args.playfield,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(report.format())
    if args.frame:
        png.write(Path(args.frame), frame.width, frame.height, frame_to_rgba(frame))
        print(f"frame written: {args.frame}")
    return 0


def _cmd_anim_nmy(args: argparse.Namespace) -> int:
    """Decode the recovered ANIM/NMY framings and report per-world counts."""
    game_dir = args.game_dir or os.environ.get("LOMAX_GAME_DIR")
    if not game_dir:
        print(
            "error: pass a game dir, or set LOMAX_GAME_DIR",
            file=sys.stderr,
        )
        return 2
    files = find_world_files(game_dir)
    if not files:
        print(f"error: no *.WLD found under {game_dir}", file=sys.stderr)
        return 2
    print(format_anim_nmy_report(probe_recovered_framings(files)))
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

    p_exp = sub.add_parser(
        "export",
        help="decode CELL/TTAB/MAP of one .WLD into PNG sheets (read-only on the source)",
    )
    p_exp.add_argument("wld_file", help="path to a WORLDS/*.WLD file")
    p_exp.add_argument("--out", required=True, help="directory for the PNG sheets")
    p_exp.add_argument(
        "--palette",
        type=int,
        default=1,
        metavar="SLOT",
        help="HEAD palette slot 0-9 (default 1; which slot the art uses is Q8)",
    )
    p_exp.add_argument(
        "--tile-layout",
        choices=("strip", "2x2"),
        default="strip",
        help="tile sheet: four cells in stored order (default) or 2x2 (G1 hypothesis)",
    )
    p_exp.add_argument("--cell-columns", type=int, default=32, help="cells per sheet row")
    p_exp.add_argument("--tile-columns", type=int, default=16, help="records per sheet row")
    p_exp.add_argument("--scale", type=int, default=2, help="integer upscale factor")
    p_exp.add_argument(
        "--map-field",
        choices=("collision", "word-hi", "word-lo"),
        default="collision",
        help="which raw MAP byte the map sheet shows as greyscale",
    )
    p_exp.set_defaults(func=_cmd_export)

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

    p_slice = sub.add_parser(
        "slice",
        help="run the headless vertical slice of the first world (read-only)",
    )
    p_slice.add_argument(
        "game_dir",
        nargs="?",
        default=None,
        help="folder containing WORLDS/*.WLD (default: $LOMAX_GAME_DIR)",
    )
    p_slice.add_argument(
        "--world",
        default="VILLAGE",
        help="world file stem to play (default: VILLAGE)",
    )
    p_slice.add_argument(
        "--ticks",
        type=int,
        default=300,
        help="maximum ticks to run (default: 300 = 5 s at 60 Hz)",
    )
    p_slice.add_argument(
        "--playfield",
        type=int,
        default=0,
        help="plane index used as the playable grid (default: 0)",
    )
    p_slice.add_argument(
        "--frame",
        metavar="PATH",
        help="also write the final frame as PNG here (outside the game folder)",
    )
    p_slice.set_defaults(func=_cmd_slice)

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

    p_anm = sub.add_parser(
        "anim-nmy",
        help="decode the recovered ANIM/NMY framings and report counts (read-only)",
    )
    p_anm.add_argument(
        "game_dir",
        nargs="?",
        default=None,
        help="folder containing WORLDS/*.WLD (default: $LOMAX_GAME_DIR)",
    )
    p_anm.set_defaults(func=_cmd_anim_nmy)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
