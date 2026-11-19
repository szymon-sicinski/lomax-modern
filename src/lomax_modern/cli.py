"""Command line interface for the Lomax research toolkit."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Callable

from . import __version__
from . import gif, png
from .art import ArtError, check_output_dir, export_world, refuse_into_game_folder
from .config import (
    UNSET,
    ConfigError,
    PresentSettings,
    default_config_path,
    load_or_create,
    resolve_settings,
    write_config,
)
from .anim_nmy import format_anim_nmy_report
from .anim_nmy import format_gnmy_report
from .anim_nmy import probe_anim_nmy as probe_recovered_framings
from .anim_nmy import probe_gnmy
from .doctor import find_world_files, format_report, inventory
from .engine.run import run_slice
from .install import check_install, is_inside_tree, resolve_world
from .measure import measure_install, summarise, to_json
from .probe_anim_nmy import format_report as format_probe_report
from .probe_anim_nmy import probe_anim_nmy
from .probe_tiles import format_report as format_tiles_report
from .probe_tiles import probe_tiles

from .presenter import (
    PresentationError,
    plan_presentation,
    present_frame,
    write_presented_png,
    write_presentation_png,
)
from .scaler import Filter
from .wld import WLDError, parse_file
from .wldscan import format_report as format_wld_report
from .wldscan import scan_file

#: ``slice`` has no presenter settings of its own, so its PNGs are exported
#: through the authentic profile: native 320x240, nearest, no letterboxing --
#: the same pixels its single-frame ``--frame`` export has always had.
SLICE_CAPTURE_SETTINGS = PresentSettings(modern=False).with_profile(False)


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


def _checked_json_path(path: str | None) -> Path | None:
    """Validate a ``--json`` destination the way ``--out``/``--frame`` are.

    ``measure`` and ``probe-anim-nmy`` write a report file, so the rule every
    other writer follows applies to them too: refuse a destination that resolves
    inside a tree holding ``LOMAX.EXE``
    (:func:`lomax_modern.art.refuse_into_game_folder`). Raises :class:`ArtError`
    so both callers print the shared message and exit 2.
    """
    if not path:
        return None
    destination = Path(path)
    refuse_into_game_folder(destination.parent)
    return destination


def _cmd_measure(args: argparse.Namespace) -> int:
    try:
        report = measure_install(args.game_dir)
    except NotADirectoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        json_path = _checked_json_path(args.json)
    except ArtError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if json_path is not None:
        json_path.write_text(to_json(report), encoding="utf-8")
    print(to_json(report) if args.quiet else summarise(report))
    return 0


def _cmd_probe_anim_nmy(args: argparse.Namespace) -> int:
    if not Path(args.game_dir).is_dir():
        print(f"error: not a directory: {args.game_dir}", file=sys.stderr)
        return 2
    report = probe_anim_nmy(args.game_dir)
    try:
        json_path = _checked_json_path(args.json)
    except ArtError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if json_path is not None:
        json_path.write_text(to_json(report), encoding="utf-8")
    print(to_json(report) if args.quiet else format_probe_report(report))
    return 0


def _cmd_probe_tiles(args: argparse.Namespace) -> int:
    if not Path(args.game_dir).is_dir():
        print(f"error: not a directory: {args.game_dir}", file=sys.stderr)
        return 2
    # Same rule as every other writer: a derived report never lands inside an
    # install. Checked before the probe runs, so the refusal does not depend on
    # the install being readable.
    try:
        json_path = _checked_json_path(args.json)
    except ArtError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = probe_tiles(args.game_dir)
    if json_path is not None:
        json_path.write_text(to_json(report), encoding="utf-8")
    print(to_json(report) if args.quiet else format_tiles_report(report))
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


def _frame_filename(index: int) -> str:
    """Deterministic per-tick name, 4 digits, so ``ffmpeg -i frame_%04d.png`` fits."""
    return f"frame_{index:04d}.png"


def _frame_sink(
    out_dir: Path, settings: PresentSettings
) -> Callable[[int, object], None]:
    """Build the ``run_slice`` frame sink: one presented PNG per tick.

    ``png.write`` creates the directory on the first frame, so an absent
    ``--out`` needs no separate mkdir (and a bad path fails once, loudly).
    """

    def sink(index: int, frame: object) -> None:
        write_presented_png(out_dir / _frame_filename(index), frame, settings)

    return sink


def _sequence_summary(out_dir: Path, count: int) -> str:
    """One deterministic line describing a written frame sequence."""
    if count:
        span = f"{_frame_filename(0)} .. {_frame_filename(count - 1)}"
    else:
        span = "none (0 ticks)"
    return f"frames: {count} PNGs in {out_dir} ({span})"


def _check_capture_args(args: argparse.Namespace) -> int | None:
    """Validate the ``--frames``/``--out`` pair; return an exit code when invalid."""
    if args.frames is not None and args.out is None:
        print(
            "error: --frames N needs --out DIR (where the PNG sequence goes)",
            file=sys.stderr,
        )
        return 2
    if args.out is not None and args.frames is None:
        print("error: --out DIR is only used with --frames N", file=sys.stderr)
        return 2
    return None


def _cmd_slice(args: argparse.Namespace) -> int:
    """Run the headless vertical slice of the first world (read-only)."""
    usage = _check_capture_args(args)
    if usage is not None:
        return usage
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
    out_dir: Path | None = None
    if args.out is not None:
        out_dir = Path(args.out).expanduser()
        try:
            check_output_dir(out_dir, Path(game_dir) / "WORLDS" / f"{args.world}.WLD")
        except ArtError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    try:
        report, frame = run_slice(
            game_dir,
            worlds=(args.world,),
            max_ticks=args.frames if args.frames is not None else args.ticks,
            playfield=args.playfield,
            on_frame=(
                _frame_sink(out_dir, SLICE_CAPTURE_SETTINGS)
                if out_dir is not None
                else None
            ),
        )
    except WLDError as exc:
        print(f"error: cannot read {args.world}.WLD: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(report.format())
    try:
        if args.frame:
            write_presented_png(Path(args.frame), frame, SLICE_CAPTURE_SETTINGS)
            print(f"frame written: {args.frame}")
        if out_dir is not None:
            print(_sequence_summary(out_dir, report.ticks))
    except (OSError, png.PNGError) as exc:
        print(f"error: cannot write frame: {exc}", file=sys.stderr)
        return 1
    return 0


def _natural_key(name: str) -> tuple[tuple[int, int | str], ...]:
    """Sort key that puts ``frame_0009.png`` before ``frame_0010.png``.

    The ``--frames`` exporter zero-pads to at least four digits, so plain
    lexicographic order already works for its output; this also keeps a mixed
    directory (``frame_9.png`` next to ``frame_10.png``) in playback order
    instead of silently scrambling it.
    """
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in re.split(r"(\d+)", name)
    )


def _frame_paths(frame_dir: Path) -> list[Path]:
    """Every ``*.png`` in ``frame_dir``, in numeric filename order."""
    return sorted(
        (
            path
            for path in frame_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".png"
        ),
        key=lambda path: _natural_key(path.name),
    )


def _read_frames(paths: list[Path]) -> tuple[int, int, list[bytes]]:
    """Decode the frame sequence, refusing one whose frames differ in size.

    A GIF has a single logical screen, so a mixed-size sequence cannot be
    written faithfully; failing here beats writing a file whose later frames are
    cropped or shifted.
    """
    width = height = 0
    frames: list[bytes] = []
    for path in paths:
        frame_width, frame_height, pixels = png.read(path)
        if not frames:
            width, height = frame_width, frame_height
        elif (frame_width, frame_height) != (width, height):
            raise gif.GIFError(
                f"frames must all be the same size: {paths[0].name} is "
                f"{width}x{height}, {path.name} is {frame_width}x{frame_height}"
            )
        frames.append(pixels)
    return width, height, frames


def _cmd_gif(args: argparse.Namespace) -> int:
    """Encode a directory of frame PNGs as one looping animated GIF89a."""
    frame_dir = Path(args.frame_dir)
    if not frame_dir.is_dir():
        print(f"error: not a directory: {frame_dir}", file=sys.stderr)
        return 2
    paths = _frame_paths(frame_dir)
    if not paths:
        print(f"error: no *.png frames in {frame_dir}", file=sys.stderr)
        return 2
    out = Path(args.out)
    try:
        refuse_into_game_folder(out.parent)
    except ArtError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    try:
        width, height, frames = _read_frames(paths)
        report = gif.write(
            out,
            width,
            height,
            frames,
            fps=args.fps,
            max_frames=args.max_frames,
        )
    except (gif.GIFError, png.PNGError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sampled = (
        f"{report.frames} of {report.frames_seen} (step {report.step})"
        if report.step > 1
        else f"{report.frames}"
    )
    print(f"frames: {sampled}, {report.width}x{report.height}")
    print(f"timing: {args.fps} fps -> {report.delay_cs} cs per frame, loops forever")
    print(f"palette: {report.palette}")
    print(f"size: {report.size} bytes")
    print(f"written: {out}")
    return 0


def _parse_surface(text: str) -> tuple[int, int]:
    """Parse ``WIDTHxHEIGHT`` (``x``, ``*`` or ``,`` accepted)."""
    cleaned = text.lower().replace(" ", "")
    for separator in ("x", "*", ","):
        if separator in cleaned:
            parts = cleaned.split(separator)
            break
    else:
        raise argparse.ArgumentTypeError(
            f"surface must be WIDTHxHEIGHT, got {text!r}"
        )
    if len(parts) != 2 or not all(parts):
        raise argparse.ArgumentTypeError(
            f"surface must be WIDTHxHEIGHT, got {text!r}"
        )
    try:
        width, height = int(parts[0]), int(parts[1])
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"surface must be two ints, got {text!r}"
        ) from None
    if width < 1 or height < 1:
        raise argparse.ArgumentTypeError(
            f"surface must be positive, got {width}x{height}"
        )
    return (width, height)


def _parse_scale(text: str) -> int | str:
    """Parse an integer factor, or ``auto`` for the largest integer fit."""
    if text.casefold() == "auto":
        return "auto"
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"scale must be a positive int or 'auto', got {text!r}"
        ) from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"scale must be >= 1, got {value}")
    return value


def _non_negative_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an int, got {text!r}") from None
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {value}")
    return value


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected an int, got {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {value}")
    return value


def _cmd_present(args: argparse.Namespace) -> int:
    """Render the engine's frame through the configured presentation.

    Read-only on the game folder: the only writes are the config file (on first
    run or with ``--save``) and the PNG export (``--frame``, or one PNG per tick
    with ``--frames N --out DIR``), all refused when they would land inside the
    install.
    """
    usage = _check_capture_args(args)
    if usage is not None:
        return usage
    requested = Path(args.game_dir).expanduser()
    manifest = check_install(requested)
    if not manifest.ok:
        print(manifest.format(), file=sys.stderr)
        print(
            f"error: not an unpacked Lomax game directory: {requested}",
            file=sys.stderr,
        )
        print(
            "hint: present expects the retail layout (WORLDS/ with *.WLD, SFX/, "
            "AMBIENT/, JINGLES/, DEMOS/, LOMAX.EXE). It never reads a disc image.",
            file=sys.stderr,
        )
        return 2
    print(manifest.format())

    config_path = (
        Path(args.config).expanduser() if args.config else default_config_path()
    )
    if is_inside_tree(config_path, manifest.root):
        print(
            f"error: refusing to write the config inside the game folder "
            f"({manifest.root}); pass --config elsewhere",
            file=sys.stderr,
        )
        return 2

    frame_path: Path | None = None
    if args.frame:
        frame_path = Path(args.frame).expanduser()
        if is_inside_tree(frame_path, manifest.root):
            print(
                f"error: --frame must not be written inside the game folder "
                f"({manifest.root}); choose a path outside it",
                file=sys.stderr,
            )
            return 2

    try:
        stored, created = load_or_create(config_path)
        settings = resolve_settings(
            stored,
            modern=args.modern,
            filter=args.filter,
            surface=args.surface,
            scale=UNSET if args.scale is None else args.scale,
        )
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    state = "created with modern defaults" if created else "existing"
    print(f"config: {config_path} ({state})")

    try:
        world_path = resolve_world(manifest, args.world)
    except LookupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_dir: Path | None = None
    if args.out is not None:
        out_dir = Path(args.out).expanduser()
        try:
            check_output_dir(out_dir, world_path)
        except ArtError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    try:
        report, frame = run_slice(
            manifest.root,
            worlds=(world_path.stem,),
            world_path=world_path,
            max_ticks=args.frames if args.frames is not None else args.ticks,
            playfield=args.playfield,
            on_frame=(
                _frame_sink(out_dir, settings) if out_dir is not None else None
            ),
        )
        plan = plan_presentation(settings, frame.width, frame.height)
        presentation = present_frame(frame, plan)
    except PresentationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except WLDError as exc:
        print(f"error: cannot read {world_path.name}: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"world: {world_path.name}")
    print(
        f"engine: {report.ticks} ticks at 60 Hz (fixed by the engine core), "
        f"{report.frames} frames, exit reached: "
        f"{'yes' if report.complete else 'no'}"
    )
    for line in plan.describe():
        print(line)

    if args.save:
        try:
            write_config(config_path, settings)
        except ConfigError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"saved: {config_path}")

    if frame_path is not None:
        surface = presentation.surface
        try:
            write_presentation_png(frame_path, presentation)
        except (OSError, png.PNGError) as exc:
            print(f"error: cannot write frame: {exc}", file=sys.stderr)
            return 1
        print(f"frame: {frame_path} ({surface.width}x{surface.height})")
    elif out_dir is not None:
        print(_sequence_summary(out_dir, report.ticks))
    else:
        print(
            "frame: none written (pass --frame PATH for a PNG; this build has no "
            "window -- the Win32 presenter remains future, docs/architecture.md §5)"
        )
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
    try:
        report = probe_recovered_framings(files)
    except WLDError as exc:
        # Mirror ``slice``/``present`` (84d41b0): a file that is not a world
        # container is a refused input -- one diagnostic line, no traceback.
        # The parse error carries no path, so name the folder, as ``no *.WLD``
        # above does.
        print(f"error: cannot read a .WLD under {game_dir}: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_anim_nmy_report(report))
    return 0


def _cmd_gnmy(args: argparse.Namespace) -> int:
    """Decode every ``GNMY`` entry and report the placement correlation."""
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
    try:
        report = probe_gnmy(files)
    except WLDError as exc:
        print(f"error: cannot read a .WLD under {game_dir}: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_gnmy_report(report))
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
    p_meas.add_argument(
        "--json",
        metavar="PATH",
        help="also write the raw report here (outside the game folder)",
    )
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
        help="tile sheet: four cells in stored order (default) or 2x2 (column-major, verified)",
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
        help="maximum ticks to run (default: 300 = 5 s at 60 Hz; --frames wins)",
    )
    p_slice.add_argument(
        "--playfield",
        type=int,
        default=0,
        help="plane index used as the playable grid (default: 0)",
    )
    slice_capture = p_slice.add_mutually_exclusive_group()
    slice_capture.add_argument(
        "--frame",
        metavar="PATH",
        help="also write the final frame as PNG here (outside the game folder)",
    )
    slice_capture.add_argument(
        "--frames",
        type=_positive_int,
        metavar="N",
        default=None,
        help="write one PNG per 60 Hz tick for N ticks (needs --out)",
    )
    p_slice.add_argument(
        "--out",
        metavar="DIR",
        default=None,
        help="directory for the --frames sequence (frame_0000.png ...; "
        "created if absent, refused inside the game folder)",
    )
    p_slice.set_defaults(func=_cmd_slice)

    p_gif = sub.add_parser(
        "gif",
        help="encode a directory of frame PNGs as one looping animated GIF89a",
    )
    p_gif.add_argument(
        "frame_dir",
        help="directory of *.png frames, as written by slice/present --frames",
    )
    p_gif.add_argument(
        "--out",
        required=True,
        metavar="PATH",
        help="GIF file to write (outside the game folder)",
    )
    p_gif.add_argument(
        "--fps",
        type=_positive_int,
        default=gif.DEFAULT_FPS,
        metavar="N",
        help=(
            "playback rate in frames per second (default: "
            f"{gif.DEFAULT_FPS}); the delay is written in centiseconds, minimum 1"
        ),
    )
    p_gif.add_argument(
        "--max-frames",
        type=_non_negative_int,
        default=0,
        metavar="N",
        help=(
            "keep at most N frames, sampled evenly (default: 0 = every frame); "
            "sampling by k and playing at 60/k fps keeps the capture's real speed"
        ),
    )
    p_gif.set_defaults(func=_cmd_gif)

    p_probe = sub.add_parser(
        "probe-anim-nmy",
        help=(
            "structural probe for ANIM/NMY/GNMY chunks: offsets, token streams "
            "and record hypotheses scored by coverage (report, not parse)"
        ),
    )
    p_probe.add_argument("game_dir", help="folder containing LOMAX.EXE")
    p_probe.add_argument(
        "--json",
        metavar="PATH",
        help="also write the raw report here (outside the game folder)",
    )
    p_probe.add_argument("--quiet", action="store_true", help="print JSON instead of the digest")
    p_probe.set_defaults(func=_cmd_probe_anim_nmy)

    p_tiles = sub.add_parser(
        "probe-tiles",
        help=(
            "validate the recovered MAP/TTAB/CELL tile pipeline and report counts "
            "(read-only; closes Q20/Q21/Q22, leaves Q33 open)"
        ),
    )
    p_tiles.add_argument("game_dir", help="folder containing LOMAX.EXE")
    p_tiles.add_argument("--json", metavar="PATH", help="also write the raw report here")
    p_tiles.add_argument("--quiet", action="store_true", help="print JSON instead of the digest")
    p_tiles.set_defaults(func=_cmd_probe_tiles)

    p_pres = sub.add_parser(
        "present",
        help="present the engine frame at an integer scale (modern defaults, config file)",
    )
    p_pres.add_argument(
        "game_dir", help="unpacked game folder in the retail layout (no ISO)"
    )
    p_pres.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="config file (default: platform config dir; written on first run)",
    )
    p_pres.add_argument(
        "--world",
        metavar="NAME",
        default=None,
        help="world stem to play (default: the first *.WLD in WORLDS/)",
    )
    p_pres.add_argument(
        "--ticks",
        type=_non_negative_int,
        default=300,
        help="maximum engine ticks to run (default: 300 = 5 s at 60 Hz; "
        "--frames wins)",
    )
    p_pres.add_argument(
        "--playfield",
        type=_non_negative_int,
        default=0,
        help="plane index used as the playable grid (default: 0)",
    )
    profile = p_pres.add_mutually_exclusive_group()
    profile.add_argument(
        "--modern",
        dest="modern",
        action="store_const",
        const=True,
        help="modern profile: widescreen surface + epx-aa filter (the default)",
    )
    profile.add_argument(
        "--authentic",
        dest="modern",
        action="store_const",
        const=False,
        help="authentic profile: native 320x240 + nearest filter",
    )
    p_pres.add_argument(
        "--filter",
        choices=tuple(item.value for item in Filter),
        default=None,
        help="filter override for this run (runtime switch)",
    )
    p_pres.add_argument(
        "--surface",
        type=_parse_surface,
        default=None,
        metavar="WxH",
        help="presentation surface override (default: from the config)",
    )
    p_pres.add_argument(
        "--scale",
        type=_parse_scale,
        default=None,
        metavar="N|auto",
        help="integer scale override, or 'auto' for the largest fit",
    )
    p_pres.add_argument(
        "--save",
        action="store_true",
        help="persist the effective settings to the config file",
    )
    present_capture = p_pres.add_mutually_exclusive_group()
    present_capture.add_argument(
        "--frame",
        metavar="PATH",
        help="also write the presented surface as PNG (outside the game folder)",
    )
    present_capture.add_argument(
        "--frames",
        type=_positive_int,
        metavar="N",
        default=None,
        help="write one presented PNG per 60 Hz tick for N ticks (needs --out)",
    )
    p_pres.add_argument(
        "--out",
        metavar="DIR",
        default=None,
        help="directory for the --frames sequence (frame_0000.png ...; "
        "created if absent, refused inside the game folder)",
    )
    p_pres.set_defaults(func=_cmd_present)
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

    p_gnmy = sub.add_parser(
        "gnmy",
        help="decode the recovered GNMY entry layout and report the placement "
        "correlation (read-only)",
    )
    p_gnmy.add_argument(
        "game_dir",
        nargs="?",
        default=None,
        help="folder containing WORLDS/*.WLD (default: $LOMAX_GAME_DIR)",
    )
    p_gnmy.set_defaults(func=_cmd_gnmy)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
