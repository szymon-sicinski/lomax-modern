"""Build synthetic chunk containers for tests.

No game bytes: every fixture is generated here from scratch.
"""

from __future__ import annotations

import struct
from typing import Iterable


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


def synthetic_world(*, endian: str = "<", order: str = "tag+size") -> bytes:
    """A plausible little world: the documented chunk order, tiny payloads."""
    payloads = {
        "WRLD": b"PS-X" + b"\0" * 4,          # 8 bytes
        "NMY": b"\0" * 16,
        "HEAD": b"\0" * 32,
        "TTAB": b"\0" * 24,
        "MAP": b"\0" * 40,
        "GNMY": b"\0" * 12,
        "ANIM": b"\0" * 20,
        "CELL": b"\0" * 28,
        "END": b"",                            # 0 bytes, still 4-aligned
    }
    return build_container(payloads.items(), order=order, endian=endian)
