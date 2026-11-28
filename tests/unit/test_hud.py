"""FL13: the HUD (``docs/file-formats.md`` §2.12.d).  Synthetic fixtures only."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from lomax_modern.engine import load_level, new_game_state, render_tiles, run_slice
from lomax_modern.engine.hud import (
    HUD_ELEMENTS,
    Hud,
    HudElement,
    HudPart,
    digits,
    hud_report,
    load_hud,
)
from lomax_modern.renderer import Framebuffer
from tests.fixtures.synth import anim_payload, backdrop_world

# 1x1 sprites; sprite byte b -> ANIM type_index b - 1; palette index = the value
# tag below (so a drawn word identifies the sprite/pose).  KLEI digit d -> byte
# d + 1 (index 1 + d); GROS digit d -> byte 11 + d (index 11 + d).
KLEI_BASE, GROS_BASE = 1, 11
EINS_B, DREI_B, VIER_B, ZWEI_B, FUNF_B = 21, 22, 23, 25, 26


def _sprites() -> tuple[bytes, ...]:
    out = []
    for i in range(10):  # KLEI
        out.append(
            anim_payload(
                1,
                width=1,
                height=1,
                type_index=KLEI_BASE + i - 1,
                pixels=bytes([KLEI_BASE + i]),
            )
        )
    for i in range(10):  # GROS
        out.append(
            anim_payload(
                1,
                width=1,
                height=1,
                type_index=GROS_BASE + i - 1,
                pixels=bytes([GROS_BASE + i]),
            )
        )
    for byte in (EINS_B, DREI_B, VIER_B, VIER_B + 1, ZWEI_B, FUNF_B):
        out.append(
            anim_payload(
                1, width=1, height=1, type_index=byte - 1, pixels=bytes([byte])
            )
        )
    return tuple(out)


def _kfs(byte: int, n: int = 1):
    return tuple((byte + i, 1, 0, 0, 0) for i in range(n))


DISPLAY = (
    "Display",
    0,
    (
        ("EINS", _kfs(EINS_B)),
        ("ZWEI", _kfs(ZWEI_B)),
        ("DREI", _kfs(DREI_B)),
        ("VIER", _kfs(VIER_B, 2)),
        ("KLEI", _kfs(KLEI_BASE, 10)),
        ("GROS", _kfs(GROS_BASE, 10)),
    ),
)
ICONS = ("Icons", 0, (("FUNF", _kfs(FUNF_B)),))


def _write_main(tmp_path: Path, records=(DISPLAY, ICONS)) -> Path:
    path = tmp_path / "MAIN.WLD"
    path.write_bytes(
        backdrop_world([{"w": 40, "h": 30}], records=records, sprites=_sprites())
    )
    return path


def _level(tmp_path: Path, with_main: bool = True):
    if with_main:
        _write_main(tmp_path)
    path = tmp_path / "L.WLD"
    path.write_bytes(backdrop_world([{"w": 40, "h": 30}]))
    return load_level(path)


class _Pal:
    @staticmethod
    def word(i: int) -> int:
        return 0x1000 + i


def _draw(hud: Hud, state) -> Framebuffer:
    fb = Framebuffer(320, 240, fill=0)
    hud.draw(fb, state, _Pal())
    return fb


def _px(fb: Framebuffer, x: int, y: int) -> int:
    return fb.pixels[y * 320 + x]


def test_four_elements_two_live_and_extensible(tmp_path: Path) -> None:
    hud = load_hud(_write_main(tmp_path))
    assert hud is not None
    assert len(HUD_ELEMENTS) == 4
    assert [e.name for e in hud.elements if e.live] == ["coins", "lives"]
    fifth = HudElement(
        "fifth",
        False,
        (HudPart(10, "Display.EINS", "sprite", (10, 10)),),
        lambda _s: 0,
    )
    bigger = Hud(hud.clips, (*hud.elements, fifth))
    assert len(bigger.elements) == 5
    assert bigger.report(new_game_state(_level(tmp_path))).splitlines()[0] == (
        "hud: 5 elements, 2 live"
    )
    assert (
        _px(_draw(bigger, new_game_state(_level(tmp_path))), 10, 10) == 0x1000 + EINS_B
    )


def test_digits_units_always_tens_when_nonzero_mod_100() -> None:
    assert digits(0) == (None, 0)
    assert digits(7) == (None, 7)
    assert digits(10) == (1, 0)
    assert digits(42) == (4, 2)
    assert digits(105) == (None, 5)
    assert digits(130) == (3, 0)


def test_live_lives_and_coins_change_the_drawn_output(tmp_path: Path) -> None:
    level = _level(tmp_path)
    hud = level.hud
    assert hud is not None
    state = new_game_state(level)
    state.lives, state.coins = 3, 0
    base = _draw(hud, state)
    # lives units (285, 43) GROS digit 3; coin units (184, 41) KLEI digit 0.
    assert _px(base, 285 + 0, 43 + 0) == 0x1000 + GROS_BASE + 3
    assert _px(base, 184, 41) == 0x1000 + KLEI_BASE + 0
    assert _px(base, 278, 43) == 0  # lives tens empty
    state.lives, state.coins = 12, 47
    moved = _draw(hud, state)
    assert _px(moved, 285, 43) == 0x1000 + GROS_BASE + 2
    assert _px(moved, 278, 43) == 0x1000 + GROS_BASE + 1
    assert _px(moved, 184, 41) == 0x1000 + KLEI_BASE + 7
    assert _px(moved, 179, 41) == 0x1000 + KLEI_BASE + 4
    # non-live: freed-lemming (138, 41) and weapon (35, 41) counts stay "0"
    for fb in (base, moved):
        assert _px(fb, 138, 41) == 0x1000 + KLEI_BASE
        assert _px(fb, 133, 41) == 0
        assert _px(fb, 35, 41) == 0x1000 + KLEI_BASE


def test_weapon_icon_is_dimmed_and_fixed_parts_stay(tmp_path: Path) -> None:
    level = _level(tmp_path)
    state = new_game_state(level)
    fb = _draw(level.hud, state)
    assert _px(fb, 27, 30) == ((0x1000 + FUNF_B) >> 1) & 0x7BEF  # [H] dim
    assert _px(fb, 160, 51) == 0x1000 + EINS_B  # box
    assert _px(fb, 130, 51) == 0x1000 + DREI_B  # figure pose 0
    assert _px(fb, 295, 51) == 0x1000 + ZWEI_B  # face
    state.tick_count = 4  # coin pose (tick >> 2) & 7 = 1 -> second keyframe
    assert _px(_draw(level.hud, state), 190, 51) == 0x1000 + VIER_B + 1
    state.tick_count = 0
    assert _px(_draw(level.hud, state), 190, 51) == 0x1000 + VIER_B


def test_hud_draws_last_and_ignores_camera(tmp_path: Path) -> None:
    level = _level(tmp_path)
    state = new_game_state(level)
    plain = dataclasses.replace(level, hud=None)
    base = render_tiles(plain, state)
    with_hud = render_tiles(level, state)
    changed = {
        i for i, (a, b) in enumerate(zip(base.pixels, with_hud.pixels)) if a != b
    }
    assert changed  # something drawn on top
    # every changed pixel is a HUD pixel, whatever the camera: move the player.
    state.player.x += 400
    state.player.y += 100
    moved = render_tiles(level, state)
    moved_base = render_tiles(plain, state)
    moved_changed = {
        i for i, (a, b) in enumerate(zip(moved_base.pixels, moved.pixels)) if a != b
    }
    assert moved_changed == changed  # same screen positions, any camera


def test_missing_records_draw_nothing_and_report(tmp_path: Path) -> None:
    level = _level(tmp_path, with_main=False)
    assert level.hud is None
    state = new_game_state(level)
    assert render_tiles(level, state).pixels == render_tiles(level, state).pixels
    assert hud_report(None, state) == "hud: not drawn (no Display/Icons record)"
    only_display = _write_main(tmp_path, records=(DISPLAY,))
    assert load_hud(only_display) is None


def test_slice_reports_hud_block(tmp_path: Path) -> None:
    (tmp_path / "WORLDS").mkdir()
    main = _write_main(tmp_path / "WORLDS")
    assert main.is_file()
    (tmp_path / "WORLDS" / "L.WLD").write_bytes(backdrop_world([{"w": 40, "h": 30}]))
    report, _frame = run_slice(tmp_path, worlds=("L",), max_ticks=3)
    lines = report.format().splitlines()
    i = lines.index("hud: 4 elements, 2 live")
    block = lines[i + 1 : i + 5]
    assert [b.split(":")[0].strip() for b in block] == [
        "weapon",
        "lemmings",
        "coins",
        "lives",
    ]
    assert "initial" in block[0] and "live" in block[2].split(";")[0]
    assert "lives: 3, coins: 0" in lines  # existing line unchanged


def test_slice_without_main_reports_fallback(tmp_path: Path) -> None:
    (tmp_path / "WORLDS").mkdir()
    (tmp_path / "WORLDS" / "L.WLD").write_bytes(backdrop_world([{"w": 40, "h": 30}]))
    report, _frame = run_slice(tmp_path, worlds=("L",), max_ticks=3)
    assert "hud: not drawn (no Display/Icons record)" in report.format().splitlines()
