"""FL10: placements drawn with their idle clips (``docs/file-formats.md`` §2.12.b).

Every fixture is synthetic (tiny ``NMY``/``ANIM`` banks built by
:mod:`tests.fixtures.synth`) — no game bytes.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from lomax_modern.engine import load_level, new_game_state, render_tiles, run_slice
from lomax_modern.engine.level import (
    GENERATOR_SPAWNED_REASON,
    PLACEMENT_HIDDEN,
    PLACEMENT_IDLE_CLIPS,
)
from lomax_modern.engine.render import COLOUR_GNMY_OTHER, draw_placed_sprites
from lomax_modern.renderer import Framebuffer
from tests.fixtures.synth import anim_payload, backdrop_world

# Sprite byte b -> ANIM type_index b - 1.
BEE_A = anim_payload(1, width=2, height=2, type_index=0, pixels=bytes([1, 0, 0, 0]))
BEE_B = anim_payload(1, width=2, height=2, type_index=1, pixels=bytes([2, 0, 0, 0]))
HENC = anim_payload(1, width=3, height=1, type_index=2, pixels=bytes([1, 2, 3]))
ROPE0 = anim_payload(1, width=1, height=1, type_index=3, pixels=bytes([4]))
ROPE1 = anim_payload(1, width=1, height=1, type_index=4, pixels=bytes([5]))

RECORDS = (
    ("Beestjes", 0x00, (("EINS", ((1, 1, 0, 0, 0),)), ("DREI", ((2, 1, 0, 0, 0),)))),
    ("Henchlemming", 0x00, (("STAY", ((3, 1, 2, 0xFFFF, 0),)),)),
    ("Rope", 0x10, (("ROPE", ((4, 1, 0, 0, 0), (5, 1, 0, 0, 0))),)),
    ("Generator", 0x00, ()),
    ("Pots", 0x00, ()),
    ("Mystery", 0x00, ()),
)
BEES, HENCH, ROPE, GEN, POTS, MYSTERY = range(6)


def _level(tmp_path: Path, gnmy: list):
    data = backdrop_world(
        [{"w": 40, "h": 30, "gnmy": gnmy}],
        records=RECORDS,
        sprites=(BEE_A, BEE_B, HENC, ROPE0, ROPE1),
    )
    path = tmp_path / "L.WLD"
    path.write_bytes(data)
    return load_level(path)


def _of(level, name: str):
    return [s for s in level.placed_sprites if s.entry.name == name]


def test_idle_clip_table_and_hidden_reasons() -> None:
    assert PLACEMENT_IDLE_CLIPS["Bees"] == ("EINS", "DREI")
    assert PLACEMENT_IDLE_CLIPS["Henc"] == ("STAY",)
    assert PLACEMENT_IDLE_CLIPS["Rope"] == ("ROPE",)
    assert PLACEMENT_IDLE_CLIPS["Jump"] == ("PAD",)
    assert PLACEMENT_IDLE_CLIPS["Mone"] == ("HANG",)
    assert PLACEMENT_IDLE_CLIPS["Exit"] == ("EXIT",)
    assert PLACEMENT_IDLE_CLIPS["Revi"] == ("EINS",)
    assert PLACEMENT_IDLE_CLIPS["Loro"] == ("HAT",)
    assert PLACEMENT_IDLE_CLIPS["Thie"] == ("STAY",)
    assert set(PLACEMENT_HIDDEN) == {"Gene", "Musi", "Ufos", "Star", "Para"}
    assert "invisible spawn trigger" in PLACEMENT_HIDDEN["Gene"]


def test_bees_pick_eins_or_drei_by_index_parity(tmp_path: Path) -> None:
    level = _level(tmp_path, [(BEES, 100, 100, 0, (), None), (BEES, 120, 100, 0, (), None)])
    first, second = level.placed_sprites
    assert first.indices[0] == 1  # EINS -> sprite byte 1
    assert second.indices[0] == 2  # DREI -> sprite byte 2
    assert (first.x, first.y) == (100, 100)


def test_hidden_by_design_and_generator_spawned(tmp_path: Path) -> None:
    gnmy = [
        (GEN, 10, 10, 0, (), None),
        (GEN, 20, 10, 0, (), None),
        (POTS, 30, 10, 0, (), None),
        (HENCH, 64, 10, 0x2000, (), None),  # spawned by a Generator
        (HENCH, 64, 20, 0, (), None),  # ordinary ones
        (HENCH, 64, 30, 0, (), None),
    ]
    report = _level(tmp_path, gnmy).placement_report
    assert (report.total, report.drawn, report.hidden_count, len(report.missing)) == (6, 2, 4, 0)
    by_name = {n: (c, r) for n, c, r in report.hidden}
    assert by_name["Generator"][0] == 2 and "invisible spawn trigger" in by_name["Generator"][1]
    assert by_name["Pots"] == (1, GENERATOR_SPAWNED_REASON)
    assert by_name["Henchlemming"] == (1, GENERATOR_SPAWNED_REASON)


def test_henchlemming_mirrored_when_x_bit_0x10(tmp_path: Path) -> None:
    level = _level(tmp_path, [(HENCH, 64, 50, 0, (), None), (HENCH, 48, 50, 0, (), None)])
    plain, flipped = level.placed_sprites
    assert plain.indices == (1, 2, 3) and plain.x == 64 + 2 and plain.y == 50 - 1
    # dx' = 1 - w - dx = 1 - 3 - 2 = -4, pixels reversed.
    assert flipped.indices == (3, 2, 1) and flipped.x == 48 - 4


def test_rope_repeats_keyframe_zero_p1_times_then_keyframe_one(tmp_path: Path) -> None:
    level = _level(tmp_path, [(ROPE, 200, 10, 0, (3,), None)])
    assert [(s.indices[0], s.y) for s in level.placed_sprites] == [
        (4, 10),
        (4, 42),
        (4, 74),
        (5, 106),
    ]
    assert level.placement_report.drawn == 1  # one placement, four layers


def test_count_line_and_hidden_lines(tmp_path: Path) -> None:
    gnmy = [(BEES, 1, 1, 0, (), None)] * 3 + [(GEN, 5, 5, 0, (), None)] * 3
    text = _level(tmp_path, gnmy).placement_report.format().splitlines()
    assert text[0] == "sprites: 3/6 drawn, 3 hidden by design, 0 missing"
    assert text[1].startswith("  hidden: Generator x3 — invisible spawn trigger [V]")


def test_unknown_name_is_missing_and_keeps_its_marker(tmp_path: Path) -> None:
    level = _level(tmp_path, [(MYSTERY, 30, 40, 0, (), None), (BEES, 8, 8, 0, (), None)])
    report = level.placement_report
    assert (report.drawn, report.hidden_count, len(report.missing)) == (1, 0, 1)
    assert report.format().startswith("sprites: 1/2 drawn, 0 hidden by design, 1 missing")
    assert [e.name for e in level.marker_entries()] == ["Mystery"]
    frame = render_tiles(level, new_game_state(level))
    assert COLOUR_GNMY_OTHER in frame.pixels


def test_offscreen_sprites_are_culled(tmp_path: Path) -> None:
    level = _level(tmp_path, [(BEES, 500, 400, 0, (), None), (GEN, 1, 1, 0, (), None)])
    sprite = level.placed_sprites[0]
    palette = type("P", (), {"word": staticmethod(lambda i: 0x1234 + i)})()
    fb = Framebuffer(320, 240, fill=0)
    draw_placed_sprites(fb, level.placed_sprites, palette, 0, 0)
    assert not any(fb.pixels)
    draw_placed_sprites(fb, level.placed_sprites, palette, sprite.x - 5, sprite.y - 7)
    assert fb.pixels[7 * 320 + 5] == 0x1234 + 1
    assert sum(1 for p in fb.pixels if p) == 1  # index 0 stays transparent
    # Just past the sprite's own edge: nothing drawn, nothing wrapped.
    fb2 = Framebuffer(320, 240, fill=0)
    draw_placed_sprites(fb2, level.placed_sprites, palette, sprite.x + 2, sprite.y + 2)
    assert not any(fb2.pixels)


def test_level_without_resolved_sprites_still_draws_all_markers(tmp_path: Path) -> None:
    level = _level(tmp_path, [(MYSTERY, 30, 40, 0, (), None), (GEN, 60, 40, 0, (), None)])
    bare = replace(level, placed_sprites=(), placement_report=None)
    assert [e.name for e in bare.marker_entries()] == ["Mystery", "Generator"]
    frame = render_tiles(bare, new_game_state(bare))
    assert COLOUR_GNMY_OTHER in frame.pixels


def test_slice_prints_the_sprites_line(tmp_path: Path) -> None:
    level = _level(tmp_path, [(BEES, 8, 8, 0, (), None), (GEN, 9, 9, 0, (), None)])
    report, _frame = run_slice(tmp_path, world_path=level.path, max_ticks=2)
    assert "sprites: 1/2 drawn, 1 hidden by design, 0 missing" in report.format()
