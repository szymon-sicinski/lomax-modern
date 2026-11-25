"""``slice``/``play`` ``--section``/``--sublevel`` and the ``level:`` line.

Synthetic data only: the executable comes from ``tests/fixtures/pe.py`` and the
worlds from ``tests/fixtures/synth.py``.  Nothing reads a game installation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lomax_modern import cli
from lomax_modern.cli import build_parser, main
from tests.fixtures.install import build_install
from tests.fixtures.pe import DEFAULT_ROWS, Row, build_exe
from tests.fixtures.synth import multi_plane_world

NAMES = ("MEDIEVAL.WLD", "VILLAGE.WLD", "PLAIN.WLD") + tuple(
    f"{c}.WLD" for c in "DEFGHIJ"
)
EXPECTED_ERROR = (
    "error: LOMAX.EXE does not have the expected section table ({check}); "
    "a different build or language is not supported here — use "
    "--world/--playfield, or the supported install"
)


def _rows() -> tuple[Row, ...]:
    rows = list(DEFAULT_ROWS)
    rows[0] = Row(0b1111, 1, 0, (0b1111,))  # MEDIEVAL: planes 0 1 2 3
    rows[1] = Row(0b1, 2, 2, (0b1,))  # PLAIN: plane 0 only
    rows[2] = Row(0b1111, 3, 1, (0b1111,))  # VILLAGE: planes 0 1 2 3
    rows[3] = Row(0b1000000001, 4, 0, (0b11,))  # MEDIEVAL: planes 0 and 9
    return tuple(rows)


@pytest.fixture
def install(tmp_path: Path) -> Path:
    root = build_install(tmp_path / "game", worlds=("MEDIEVAL", "VILLAGE", "PLAIN"))
    worlds = root / "WORLDS"
    four = multi_plane_world([[3], [0, 3, 1, 2], [], [1]])
    (worlds / "MEDIEVAL.WLD").write_bytes(four)
    (worlds / "VILLAGE.WLD").write_bytes(four)
    (worlds / "PLAIN.WLD").write_bytes(multi_plane_world([[3]]))
    build_exe(rows=_rows(), names=NAMES, write_to=root / "LOMAX.EXE")
    return root


def _run(capsys, *argv: str):
    code = main(list(argv))
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def test_section_prints_level_and_playfield_lines(install, capsys) -> None:
    code, out, err = _run(
        capsys,
        "slice",
        str(install),
        "--section",
        "0",
        "--sublevel",
        "0",
        "--ticks",
        "2",
    )
    assert code == 0, err
    lines = out.splitlines()
    assert lines[0] == (
        "level: section 0 sub-level 0 = MEDIEVAL, playfield plane 0, "
        "backdrop planes 1 2 3"
    )
    assert out.count("playfield: 2x2 cells (32x32 px)") == 1


def test_section_without_backdrop_planes(install, capsys) -> None:
    code, out, _ = _run(capsys, "slice", str(install), "--section", "1", "--ticks", "2")
    assert code == 0
    assert out.splitlines()[0] == (
        "level: section 1 sub-level 0 = PLAIN, playfield plane 0, backdrop planes none"
    )


def test_bad_exe_is_one_line_error_and_no_world_opened(
    install, capsys, monkeypatch
) -> None:
    (install / "LOMAX.EXE").write_bytes(b"MZ")
    for name in ("load_level", "run_slice", "parse_file"):
        monkeypatch.setattr(
            cli, name, lambda *a, **k: pytest.fail("a world was opened"), raising=False
        )
    monkeypatch.setattr(
        cli._wld_mod, "parse_file", lambda *a, **k: pytest.fail("a world was opened")
    )
    out_dir = install.parent / "frames"
    code, out, err = _run(
        capsys,
        "slice",
        str(install),
        "--section",
        "0",
        "--frames",
        "2",
        "--out",
        str(out_dir),
    )
    assert code == 2
    assert out == ""
    assert not out_dir.exists()
    (line,) = err.splitlines()
    assert line.startswith(EXPECTED_ERROR.split("{check}")[0])
    assert line.endswith(EXPECTED_ERROR.split("{check}")[1])
    assert "Traceback" not in err


def test_no_worlds_dir_still_reports_exe_error(tmp_path, capsys) -> None:
    root = tmp_path / "bare"
    root.mkdir()
    (root / "LOMAX.EXE").write_bytes(b"MZ")
    code, _, err = _run(capsys, "slice", str(root), "--section", "0")
    assert code == 2 and len(err.splitlines()) == 1


def test_missing_exe(install, capsys) -> None:
    (install / "LOMAX.EXE").unlink()
    code, _, err = _run(capsys, "slice", str(install), "--section", "0")
    assert code == 2
    assert err.strip() == EXPECTED_ERROR.format(check="LOMAX.EXE not found")


def test_section_out_of_range(install, capsys) -> None:
    code, out, err = _run(capsys, "slice", str(install), "--section", "24")
    assert code == 2 and out == ""
    assert err.startswith("error: section 24 is outside 0..23")
    code, _, err = _run(
        capsys, "slice", str(install), "--section", "0", "--sublevel", "1"
    )
    assert code == 2 and err.startswith("error: sub-level 1 of section 0")


def test_plane_missing_from_world(install, capsys) -> None:
    code, out, err = _run(capsys, "slice", str(install), "--section", "3")
    assert code == 2 and out == ""
    assert err.strip() == EXPECTED_ERROR.format(
        check="plane 9 is missing from MEDIEVAL.WLD"
    )


def test_section_conflicts_with_world_and_playfield(install, capsys) -> None:
    for extra in (["--world", "VILLAGE"], ["--playfield", "0"]):
        code, _, err = _run(capsys, "slice", str(install), "--section", "0", *extra)
        assert code == 2 and err.startswith("error:")
    code, _, _ = _run(capsys, "slice", str(install), "--sublevel", "0")
    assert code == 2


def test_world_reverse_lookup(install, capsys) -> None:
    code, out, err = _run(
        capsys, "slice", str(install), "--world", "VILLAGE", "--ticks", "2"
    )
    assert code == 0, err
    assert out.splitlines()[0] == (
        "level: section 2 sub-level 0 = VILLAGE, playfield plane 0, "
        "active planes 0 1 2 3"
    )
    assert "world: VILLAGE (4 planes" in out


@pytest.mark.parametrize("exe", [b"MZ", None])
def test_world_with_unusable_exe_still_loads(install, capsys, exe) -> None:
    if exe is None:
        (install / "LOMAX.EXE").unlink()
    else:
        (install / "LOMAX.EXE").write_bytes(exe)
    code, out, err = _run(
        capsys, "slice", str(install), "--world", "VILLAGE", "--ticks", "2"
    )
    assert code == 0, err
    first = out.splitlines()[0]
    assert first.startswith(
        "level: world VILLAGE, playfield plane 0 (section unknown: "
    )
    assert "world: VILLAGE (4 planes" in out


def test_default_world_unchanged_without_flags(install, capsys) -> None:
    code, out, _ = _run(capsys, "slice", str(install), "--ticks", "2")
    assert code == 0
    assert out.splitlines()[0].startswith("level: section 2 sub-level 0 = VILLAGE")


def test_play_parses_section_flags() -> None:
    args = build_parser().parse_args(
        ["play", "dir", "--section", "3", "--sublevel", "1"]
    )
    assert (args.section, args.sublevel, args.world, args.playfield) == (
        3,
        1,
        "VILLAGE",
        0,
    )
    args = build_parser().parse_args(["play", "dir"])
    assert args.section is None and args.sublevel is None


def test_play_section_conflict_and_bad_exe(install, capsys) -> None:
    code, _, _ = _run(
        capsys, "play", str(install), "--section", "0", "--world", "VILLAGE"
    )
    assert code == 2
    (install / "LOMAX.EXE").write_bytes(b"MZ")
    code, _, err = _run(capsys, "play", str(install), "--section", "0")
    assert code == 2
    assert "does not have the expected section table" in err
