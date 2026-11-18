"""Validated decode and probe for the ``MAP`` / ``TTAB`` / ``CELL`` tile pipeline.

The corrected layouts below were recovered by static analysis of the retail
``LOMAX.EXE`` readers and **validated against the retail install**; they are
documented in ``docs/file-formats.md`` §2.4/§2.8 and close the open questions
Q20/Q21/Q22 (``docs/research/05-open-questions.md``):

* ``MAP`` — ``N`` big-endian ``u16`` tile words, then ``N`` collision bytes,
  padded to a multiple of 4.  The map word is a **direct index** into the
  plane's ``TTAB`` record array (the superseded "3 bytes per cell interleaved"
  reading is scored below and loses).
* ``TTAB`` — 16-byte records = eight big-endian ``u16`` words = four cells of
  ``[index word, flag word]``.  The index word is a 16-bit ``CELL`` index; the
  flag word carries a flip in bits 13-14 (``0x2000`` horizontal, ``0x4000``
  vertical, ``0x6000`` both) and a palette index in bits 8-11 (``0xf00``).

This module is a *probe*, not an asset exporter: it reports counts, offsets and
scoreboard results, and never emits a pixel, a tile or a payload.  No game
bytes leave it — everything is computed at run time against the user's install.
"""

from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .doctor import find_world_files
from .wld import parse_file

#: Bytes in one ``TTAB`` record (a 16x16 tile: four 8x8 cells x two words).
TTAB_RECORD_SIZE = 16

#: Cells (8x8 blocks) per ``TTAB`` record.
TTAB_CELLS = 4

#: Flip flags live in bits 13-14 of a ``TTAB`` *flag* word.
FLIP_MASK = 0x6000
FLIP_H = 0x2000  # horizontal flip
FLIP_V = 0x4000  # vertical flip

#: Palette index lives in bits 8-11 of a ``TTAB`` *flag* word.
PALETTE_MASK = 0x0F00

#: Bits a flag word never sets in retail data (bits 0-7, 12 and 15).
FLAG_UNUSED_MASK = ~(FLIP_MASK | PALETTE_MASK) & 0xFFFF

#: The superseded "13-bit cell index per word" reading of a TTAB record; kept
#: only so the report can show it losing to the 16-bit index/flag pairing.
OLD_TTAB_INDEX_MASK = 0x1FFF


@dataclass(frozen=True)
class TileSlot:
    """One cell of a ``TTAB`` record: a ``CELL`` index plus its flag word."""

    index: int
    flags: int

    @property
    def flip(self) -> int:
        return self.flags & FLIP_MASK

    @property
    def palette(self) -> int:
        return (self.flags & PALETTE_MASK) >> 8

    @property
    def has_unused_flag_bits(self) -> bool:
        return bool(self.flags & FLAG_UNUSED_MASK)


def split_map(payload: bytes, cells: int) -> tuple[tuple[int, ...], bytes]:
    """Split a ``MAP`` payload into ``cells`` big-endian words then ``cells`` bytes.

    The recovered layout is ``[N big-endian u16 tile words][N collision bytes]``
    (plus 0-3 pad bytes to a multiple of 4).  ``cells`` is the 16x16-cell count
    derived from the sibling ``HEAD`` dimensions; the pad is left to the caller.
    """
    if 2 * cells > len(payload):
        raise ValueError(
            f"MAP payload is {len(payload)} bytes, need at least {2 * cells} for "
            f"{cells} tile words"
        )
    words = struct.unpack(">" + "H" * cells, payload[: 2 * cells])
    collisions = payload[2 * cells : 3 * cells]
    return words, collisions


def split_ttab(payload: bytes) -> tuple[TileSlot, ...]:
    """Split a ``TTAB`` payload into 16-byte records of four (index, flags) cells."""
    if len(payload) % TTAB_RECORD_SIZE:
        raise ValueError(
            f"TTAB payload is {len(payload)} bytes, not a multiple of "
            f"{TTAB_RECORD_SIZE}"
        )
    slots: list[TileSlot] = []
    for record in range(len(payload) // TTAB_RECORD_SIZE):
        base = record * TTAB_RECORD_SIZE
        words = struct.unpack(
            ">" + "H" * (TTAB_RECORD_SIZE // 2), payload[base : base + TTAB_RECORD_SIZE]
        )
        for cell in range(TTAB_CELLS):
            slots.append(TileSlot(index=words[2 * cell], flags=words[2 * cell + 1]))
    return tuple(slots)


def _plane_sections(world) -> list[dict]:
    """Pair each ``HEAD`` with the ``TTAB``/``MAP`` that follow it (retail order)."""
    sections: list[dict] = []
    pending: dict = {}
    for chunk in world.chunks:
        if chunk.tag == "HEAD":
            pending = {"HEAD": chunk}
        elif chunk.tag in ("TTAB", "MAP") and "HEAD" in pending:
            pending[chunk.tag] = chunk
            if "TTAB" in pending and "MAP" in pending:
                sections.append(pending)
                pending = {}
    return sections


def _dimensions(head_chunk) -> tuple[int, int]:
    """Plane width/height in 8-pixel units (big-endian), docs §2.3 ``[V]``."""
    return struct.unpack(">II", head_chunk.payload[:8])


def probe_tiles(game_dir: str | Path) -> dict:
    """Validate the recovered MAP/TTAB layouts on every plane and count them.

    Read-only.  Returns a JSON-serialisable report of counts, the flag/palette
    distributions, and the scores of the *superseded* readings so a wrong
    assumption is visible in the output instead of hidden.
    """
    totals: dict = {
        "map_words": 0,
        "distinct_map_words": set(),
        "map_out_of_bank": 0,
        "map_max_word": -1,
        "ttab_records": 0,
        "ttab_slots": 0,
        "index_out_of_bank": 0,
        "distinct_indices": set(),
        "index_max": -1,
    }
    flag_flip: Counter = Counter()
    flag_palette: Counter = Counter()
    flag_unused = 0
    collision: Counter = Counter()
    # Superseded readings, scored only.
    old_interleaved_oob = 0
    old_interleaved_total = 0
    old_13bit_oob = 0
    old_13bit_oob_detail: Counter = Counter()

    worlds: list[dict] = []
    planes_total = 0
    for path in find_world_files(game_dir):
        world = parse_file(path)
        cell_chunk = next((c for c in world.chunks if c.tag == "CELL"), None)
        cell_count = len(cell_chunk.payload) // 64 if cell_chunk else 0
        world_info = {
            "name": path.name,
            "planes": 0,
            "cell_count": cell_count,
            "ttab_records": 0,
            "map_words": 0,
            "map_max_word": -1,
        }
        for section in _plane_sections(world):
            planes_total += 1
            width_units, height_units = _dimensions(section["HEAD"])
            cells = (width_units * 8 // 16) * (height_units * 8 // 16)
            words, collisions = split_map(section["MAP"].payload, cells)
            slots = split_ttab(section["TTAB"].payload)
            tile_count = len(slots) // TTAB_CELLS

            for word in words:
                totals["map_words"] += 1
                totals["distinct_map_words"].add(word)
                totals["map_max_word"] = max(totals["map_max_word"], word)
                world_info["map_max_word"] = max(world_info["map_max_word"], word)
                if word >= tile_count:
                    totals["map_out_of_bank"] += 1
            world_info["map_words"] += len(words)

            for slot in slots:
                totals["ttab_slots"] += 1
                totals["distinct_indices"].add(slot.index)
                totals["index_max"] = max(totals["index_max"], slot.index)
                flag_flip[slot.flip] += 1
                flag_palette[slot.palette] += 1
                if slot.has_unused_flag_bits:
                    flag_unused += 1
                if slot.index >= cell_count:
                    totals["index_out_of_bank"] += 1
            totals["ttab_records"] += tile_count
            world_info["ttab_records"] += tile_count

            for byte in collisions:
                collision[byte] += 1

            # Superseded readings, for the scoreboard only.
            payload = section["MAP"].payload
            for i in range(cells):
                old_interleaved_total += 1
                interleaved_word = struct.unpack(">H", payload[3 * i : 3 * i + 2])[0]
                if interleaved_word >= tile_count:
                    old_interleaved_oob += 1
            for slot in slots:
                for word16 in (slot.index, slot.flags):
                    if (word16 & OLD_TTAB_INDEX_MASK) >= cell_count:
                        old_13bit_oob += 1
                        if path.name == "BONUS.WLD" and (word16 & OLD_TTAB_INDEX_MASK) == 256:
                            old_13bit_oob_detail["BONUS index 256 (flag word 0x0100)"] += 1

            world_info["planes"] += 1
        worlds.append(world_info)

    report = {
        "game_dir": str(Path(game_dir)),
        "worlds": worlds,
        "planes": planes_total,
        "map": {
            "words": totals["map_words"],
            "distinct_words": len(totals["distinct_map_words"]),
            "out_of_bank": totals["map_out_of_bank"],
            "max_word": totals["map_max_word"],
        },
        "ttab": {
            "records": totals["ttab_records"],
            "slots": totals["ttab_slots"],
            "distinct_indices": len(totals["distinct_indices"]),
            "index_max": totals["index_max"],
            "index_out_of_bank": totals["index_out_of_bank"],
            "flag_flip_counts": {f"{k:#06x}": flag_flip[k] for k in sorted(flag_flip)},
            "flag_palette_counts": {str(k): flag_palette[k] for k in sorted(flag_palette)},
            "flag_words_with_unused_bits": flag_unused,
        },
        "collision": {
            "bytes": sum(collision.values()),
            "distinct_values": len(collision),
            "zero_count": collision[0],
        },
        "superseded_hypothesis_scores": {
            "map_interleaved_out_of_bank": old_interleaved_oob,
            "map_interleaved_total": old_interleaved_total,
            "ttab_13bit_index_out_of_bank": old_13bit_oob,
            "ttab_13bit_bonus_256_count": old_13bit_oob_detail.get(
                "BONUS index 256 (flag word 0x0100)", 0
            ),
        },
    }
    return report


def format_report(report: dict) -> str:
    """Human-readable digest of :func:`probe_tiles` (counts only)."""
    m = report["map"]
    t = report["ttab"]
    c = report["collision"]
    s = report["superseded_hypothesis_scores"]
    lines = [
        "probe: MAP -> TTAB -> CELL tile pipeline (validated decode, counts only)",
        f"game_dir: {report['game_dir']}",
        f"planes: {report['planes']}",
        "",
        "MAP (N big-endian u16 tile words, then N collision bytes):",
        f"  words {m['words']}, distinct {m['distinct_words']}, "
        f"max {m['max_word']}, out-of-bank {m['out_of_bank']} "
        "(map word = direct TTAB record index, Q20)",
        "",
        "TTAB (16-byte records = 4 x [index word, flag word]):",
        f"  records {t['records']} (slots {t['slots']}), distinct CELL indices "
        f"{t['distinct_indices']} (max {t['index_max']}), "
        f"index out-of-bank {t['index_out_of_bank']} (Q22: none -> flag words, not indices)",
        "  flag word flips (bits 13-14): "
        + ", ".join(f"{k} {v}" for k, v in t["flag_flip_counts"].items())
        + "  (0x2000 H, 0x4000 V, 0x6000 both; Q21)",
        "  flag word palettes (bits 8-11): "
        + ", ".join(f"slot {k}: {v}" for k, v in t["flag_palette_counts"].items()),
        f"  flag words with unused bits set (0-7/12/15): {t['flag_words_with_unused_bits']}",
        "",
        "CELL collision bytes:",
        f"  {c['bytes']} bytes, {c['distinct_values']} distinct values, "
        + (
            f"{c['zero_count']} zero ({100.0 * c['zero_count'] / c['bytes']:.1f}%)"
            if c["bytes"]
            else "0 zero (no planes read)"
        ),
        "",
        "Superseded readings (scoreboard only):",
        f"  MAP interleaved (3 B/cell): {s['map_interleaved_out_of_bank']}/"
        f"{s['map_interleaved_total']} words out of bank",
        f"  TTAB 13-bit index on every word: {s['ttab_13bit_index_out_of_bank']} "
        f"out of bank; BONUS 'index 256' = "
        f"{s['ttab_13bit_bonus_256_count']} flag words (palette 1 = 0x0100)",
    ]
    return "\n".join(lines) + "\n"
