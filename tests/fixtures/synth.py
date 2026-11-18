"""Build synthetic chunk containers for tests.

No game bytes: every fixture is generated here from scratch. Sizes and layouts
mirror what the retail PC files were measured to contain (see
``docs/file-formats.md``): a 4-byte tag, a big-endian or little-endian ``u32``
payload size, and the chunk order
``WRLD, NMY, PARA, (HEAD, TTAB, MAP, GNMY)*, CELL, ANIM, MACR, PAGE, END``.
"""

from __future__ import annotations

import struct
from typing import Iterable, Sequence


def build_container(
    chunks: Iterable[tuple[str, bytes]],
    *,
    order: str = "tag+size",
    endian: str = "<",
) -> bytes:
    """Serialise ``chunks`` as a tag/size container.

    ``order`` is "tag+size" (tag first) or "size+tag"; ``endian`` is "<" or ">".
    Sizes are payload-only and must be multiples of 4 (the documented rule).
    """
    out = bytearray()
    for tag, payload in chunks:
        if not 1 <= len(tag) <= 4:
            raise ValueError(f"tag must be 1-4 chars: {tag!r}")
        if len(payload) % 4:
            raise ValueError(f"payload of {tag} must be a multiple of 4 bytes")
        size = struct.pack(endian + "I", len(payload))
        # The header field is four bytes; short tags are space-padded.
        tag_b = tag.encode("ascii").ljust(4, b" ")
        out += tag_b + size if order == "tag+size" else size + tag_b
        out += payload
    return bytes(out)


def head_payload(
    width_units: int,
    height_units: int,
    *,
    endian: str = ">",
    palettes: "Sequence[Sequence[int]] | None" = None,
) -> bytes:
    """A HEAD payload: plane width/height in 8-pixel units plus zeroed fields.

    The real payload is 5240 bytes (10 palettes, editor data, ANIM bitmap); the
    fixture keeps the two leading SIZE fields and pads the rest, which is all
    the measurement code reads.

    ``palettes`` optionally supplies up to 10 slots of 256 15-bit colours each,
    written little-endian at the documented offset 8, for palette tests.
    """
    body = struct.pack(endian + "II", width_units, height_units)
    if palettes is None:
        return body + b"\0" * (5240 - len(body))
    block = bytearray(5120)
    for slot, words in enumerate(palettes):
        if len(words) != 256:
            raise ValueError(f"palette slot {slot} holds {len(words)} words, expected 256")
        struct.pack_into("<256H", block, slot * 512, *words)
    return body + bytes(block) + b"\0" * (5240 - len(body) - len(block))


def cell_payload(blocks: Iterable[bytes | Sequence[int]]) -> bytes:
    """A CELL payload: 64-byte 8x8 blocks, as raw bytes or 64 palette indices."""
    out = bytearray()
    for block in blocks:
        raw = bytes(block)
        if len(raw) != 64:
            raise ValueError(f"cell block is {len(raw)} bytes, expected 64")
        out += raw
    return bytes(out)


def ttab_payload(records: Iterable[Sequence[int]]) -> bytes:
    """A TTAB payload: 8-byte records of four big-endian u16 cell-index words."""
    out = bytearray()
    for record in records:
        if len(record) != 4:
            raise ValueError(f"tile record holds {len(record)} words, expected 4")
        for word in record:
            if not 0 <= word <= 0xFFFF:
                raise ValueError(f"tile word {word} does not fit in a u16")
        out += struct.pack(">4H", *record)
    return bytes(out)


def map_payload(
    width_units: int,
    height_units: int,
    *,
    cells: Iterable[tuple[int, int]] | None = None,
) -> bytes:
    """A MAP payload: 3 bytes per 16x16 cell, padded to a multiple of 4.

    Measured on all 104 retail sections: ``size - 3 * cells`` is 0..3 and the
    payload size is always a multiple of 4.  ``cells`` supplies ``(tile_word,
    collision)`` pairs; the default fills zeros.
    """
    count = (width_units * 8 // 16) * (height_units * 8 // 16)
    if cells is None:
        raw = b"\0" * (count * 3)
    else:
        out = bytearray()
        for tile_word, collision in cells:
            out += struct.pack(">H", tile_word) + bytes((collision,))
        if len(out) != count * 3:
            raise ValueError(f"{len(out) // 3} map cells supplied, expected {count}")
        raw = bytes(out)
    return raw + b"\0" * (-len(raw) % 4)


def gnmy_payload(types: Iterable[int] = (), *, trailer: int = 4) -> bytes:
    """A GNMY payload: entries of ``u16 size, u16 type`` plus a short trailer."""
    out = bytearray()
    for t in types:
        out += struct.pack("<HH", 8, t) + b"\0" * 4
    out += b"\0" * (-len(out) % 4)
    out += b"\0" * trailer
    return bytes(out)


def anim_payload(
    frame_count: int = 1,
    *,
    packed: bool = False,
    width: int = 8,
    height: int = 8,
    type_index: int = 0,
    flags: int = 0,
) -> bytes:
    """An ``ANIM`` payload built to the recovered framing (docs §2.6).

    Header is 12 little-endian bytes (``a, b, n, flags, type_index, pad``);
    each frame is ``i16 width, i16 height, u16 d, u16 e`` followed by
    ``round4(w*h)`` (or ``round4((w*h)>>1)`` when ``packed``) pixel bytes.
    """
    flag_word = flags | (0x8000 if packed else 0)
    out = bytearray(struct.pack("<6H", 1, 2, frame_count, flag_word, type_index, 0))
    area = width * height
    pixels = (area >> 1) if packed else area
    pixel_bytes = (pixels + 3) & ~3
    for _ in range(frame_count):
        out += struct.pack("<hhHH", width, height, 0, 0)
        out += b"\0" * pixel_bytes
    return bytes(out)


def nmy_payload(
    names: Iterable[tuple[str, int]] = (("Type", 0),),
    *,
    trailer: int = 2,
) -> bytes:
    """An ``NMY`` payload built to the recovered framing (docs §2.5).

    ``names`` is ``(name, animation_count)`` pairs.  Each record is a
    NUL-terminated name padded to a ``u16`` name-field size, then ``W_A``,
    ``W_B`` and (for each animation) a tag, a size field and one empty frame.
    The table ends with a ``u16`` zero terminator plus ``trailer`` zero bytes.
    """
    out = bytearray()

    def emit_record(name: bytes, n_anim: int) -> None:
        nonlocal out
        name_field = name + b"\0"
        size = len(name_field)
        size += (-size % 4)  # name field padded to a multiple of 4
        out += struct.pack("<H", size)
        out += name_field
        out += b"\0" * (size - len(name_field))
        out += struct.pack("<H", 0x0010)  # W_A
        out += struct.pack("<H", n_anim)  # W_B
        out += b"\0" * 2  # gap1
        for i in range(n_anim):
            out += struct.pack("<I", 0x48414E47)  # tag (arbitrary 4 bytes)
            out += struct.pack("<I", 20 + 8 * 1)  # size field == 20 + 8*frames
            out += struct.pack("<H", 1)  # count2 = 1 frame
            out += b"\0" * 18  # 9 x u16 fields
            out += b"\0" * 8  # one 8-byte frame

    for name, n_anim in names:
        emit_record(name.encode("ascii"), n_anim)
    out += b"\0" * 2  # u16 terminator
    out += b"\0" * trailer
    return bytes(out)



def synthetic_world(
    *,
    endian: str = "<",
    order: str = "tag+size",
    planes: Iterable[tuple[int, int]] = ((40, 30),),
) -> bytes:
    """A plausible little world: the retail chunk order, tiny payloads."""
    chunks: list[tuple[str, bytes]] = [
        ("WRLD", b"PS-X" + b"\0" * 4),  # 8 bytes
        ("NMY", b"\0" * 16),
        ("PARA", b"\0" * 8),
    ]
    for width_units, height_units in planes:
        chunks += [
            ("HEAD", head_payload(width_units, height_units, endian=endian)),
            ("TTAB", b"\0" * 24),
            ("MAP", map_payload(width_units, height_units)),
            ("GNMY", gnmy_payload((0,))),
        ]
    chunks += [
        ("MACR", b"\0" * 8),
        ("PAGE", b"\0" * 8),
        ("CELL", b"\0" * 64),
        ("ANIM", b"\0" * 20),
        ("END", b""),
    ]
    return build_container(chunks, order=order, endian=endian)
