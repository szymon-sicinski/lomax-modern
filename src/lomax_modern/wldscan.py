"""Chunk/tag scanner for Lomax ``.WLD`` world files.

This is deliberately a *scanner*, not a parser.  The chunk header layout used
by the game is a hypothesis taken from public reverse-engineering notes; it has
not been confirmed against a real ``.WLD`` file inside this repository, because
no game data is distributed here (see ``docs/file-formats.md``, "Confidence").

So the scanner:

* tries every plausible header convention (tag+size vs size+tag, little vs big
  endian, size = payload-only vs size = header+payload),
* scores each convention by how cleanly the chunk chain terminates at EOF,
* reports tag names, header offsets and payload offsets only,
* decodes no payload bytes at all.

If two conventions explain the same file equally well, the result is marked
``ambiguous`` and nothing should be trusted from it beyond the tag list.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

#: Tags documented for the PC world files, in the order the game reads them.
#: Three of them are shorter than the four-byte header field, so the field is
#: assumed to be space-padded ("NMY ", "MAP ", "END ") -- an unverified
#: assumption, see docs/file-formats.md.
KNOWN_TAGS: tuple[str, ...] = (
    "WRLD",
    "NMY",
    "HEAD",
    "TTAB",
    "MAP",
    "GNMY",
    "ANIM",
    "CELL",
    "END",
)

_LAYOUTS: tuple[tuple[str, str, str], ...] = tuple(
    (order, endian, semantics)
    for order in ("tag+size", "size+tag")
    for endian in ("<", ">")
    for semantics in ("payload", "inclusive")
)


@dataclass(frozen=True)
class Chunk:
    """One chunk header found in the file."""

    tag: str
    header_offset: int
    payload_offset: int
    payload_size: int
    declared_size: int
    known: bool


@dataclass
class ScanResult:
    path: str
    file_size: int
    layout: str | None
    confidence: str
    chunks: list[Chunk] = field(default_factory=list)
    coverage: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def tags(self) -> list[str]:
        return [c.tag for c in self.chunks]


def _walk(
    data: bytes, order: str, endian: str, semantics: str
) -> tuple[list[Chunk], int]:
    """Walk the chunk chain under one header hypothesis.

    Returns the chunks found and the byte offset where the chain stopped.
    """
    chunks: list[Chunk] = []
    pos = 0
    n = len(data)
    while pos + 8 <= n:
        head = data[pos : pos + 8]
        if order == "tag+size":
            tag_raw, size_raw = head[:4], head[4:]
        else:
            size_raw, tag_raw = head[:4], head[4:]

        if not all(0x20 <= b < 0x7F for b in tag_raw):
            break
        tag = tag_raw.decode("ascii").rstrip(" \0")

        declared = struct.unpack(endian + "I", size_raw)[0]
        if declared % 4 != 0:
            break
        if semantics == "payload":
            payload_size, total = declared, declared + 8
        else:
            if declared < 8:
                break
            payload_size, total = declared - 8, declared

        if total <= 0 or pos + total > n:
            break

        chunks.append(
            Chunk(
                tag=tag,
                header_offset=pos,
                payload_offset=pos + 8,
                payload_size=payload_size,
                declared_size=declared,
                known=tag in KNOWN_TAGS,
            )
        )
        pos += total

    return chunks, pos


def _score(chunks: list[Chunk], stopped_at: int, file_size: int) -> tuple:
    """Rank a hypothesis. Higher is better; ties mean a genuine ambiguity."""
    coverage = stopped_at / file_size if file_size else 0.0
    known = sum(1 for c in chunks if c.known)
    ends_with_end = bool(chunks) and chunks[-1].tag == "END"
    return (
        1 if stopped_at == file_size else 0,
        round(coverage, 6),
        len(chunks),
        known,
        1 if ends_with_end else 0,
    )


def scan_bytes(data: bytes, path: str = "<memory>") -> ScanResult:
    """Scan ``data`` for a chunk chain and pick the best-fitting layout."""
    scored = []
    for order, endian, semantics in _LAYOUTS:
        chunks, stopped_at = _walk(data, order, endian, semantics)
        if not chunks:
            continue
        scored.append(
            (
                _score(chunks, stopped_at, len(data)),
                f"{order} u32{'le' if endian == '<' else 'be'} ({semantics})",
                chunks,
                stopped_at,
            )
        )

    result = ScanResult(
        path=path,
        file_size=len(data),
        layout=None,
        confidence="no-chain",
    )
    if not scored:
        result.notes.append(
            "no 4-byte-tag + 4-byte-size chain fits this file; "
            "the file may not be a chunk container"
        )
        return result

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_layout, best_chunks, best_stop = scored[0]
    tied = [s for s in scored if s[0] == best_score]

    result.layout = best_layout
    result.chunks = best_chunks
    result.coverage = best_stop / len(data) if data else 0.0
    result.confidence = "ambiguous" if len(tied) > 1 else (
        "confirmed-chain" if best_stop == len(data) else "partial-chain"
    )

    if len(tied) > 1:
        result.notes.append(
            "several header conventions explain this file equally well: "
            + ", ".join(s[1] for s in tied)
            + " -- treat offsets as unverified"
        )
    if best_stop != len(data):
        result.notes.append(
            f"chain stops at byte {best_stop} of {len(data)} "
            f"({best_stop - best_stop % 4} bytes consumed); trailing bytes are "
            "not explained by this layout"
        )
    if not any(c.known for c in best_chunks):
        result.notes.append(
            "no chunk tag matches the documented set "
            f"({', '.join(KNOWN_TAGS)}); check the file is a world file"
        )
    else:
        unknown = sorted({c.tag for c in best_chunks if not c.known})
        if unknown:
            result.notes.append(
                "tags outside the documented set: "
                + ", ".join(unknown)
                + " (extra data, or the wrong file)"
            )
    return result


def scan_file(path: str | Path) -> ScanResult:
    p = Path(path)
    return scan_bytes(p.read_bytes(), path=str(p))


def format_report(result: ScanResult) -> str:
    lines = [
        f"file:       {result.path}",
        f"size:       {result.file_size} bytes",
        f"layout:     {result.layout or 'unknown'}",
        f"confidence: {result.confidence}"
        f"  (coverage {result.coverage * 100:.1f}%)",
        "",
        f"{'tag':<6}{'header':>10}{'payload':>10}{'size':>10}  note",
    ]
    for c in result.chunks:
        note = "" if c.known else "undocumented tag"
        lines.append(
            f"{c.tag:<6}{c.header_offset:>10}{c.payload_offset:>10}"
            f"{c.payload_size:>10}  {note}"
        )
    for note in result.notes:
        lines.append("")
        lines.append(f"note: {note}")
    return "\n".join(lines)
