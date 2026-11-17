"""Read-only measurement probes for a Lomax installation.

Every number this module reports is either read straight from a file header or
explicitly labelled as unverified. It never writes to the game folder and never
copies asset bytes: sizes, counts, offsets and header fields only.

Measured facts this module now relies on (all re-checked on the retail PC
install, 2026-11-16, and reproducible with ``lomax-modern measure``):

* chunk header is a 4-byte tag plus a big-endian ``u32`` payload size; the
  chain reaches EOF in all 9 world files;
* ``HEAD`` carries plane width and height as big-endian ``u32`` in 8-pixel
  units, and the following ``MAP`` holds 3 bytes per 16x16 cell, padded up to a
  4-byte boundary;
* ``CELL`` payloads are a whole number of 64-byte 8x8 cells.

Anything beyond that — ``ANIM`` record layout, ``GNMY`` type names, palette
indexing — is reported as an observation, never as a format.
"""

from __future__ import annotations

import json
import struct
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .doctor import EXPECTED_DIRS, EXPECTED_FILES, find_world_files, inventory
from .wldscan import KNOWN_TAGS, Chunk, ScanResult, scan_bytes

#: Tags that occur in retail files but are not in the loader's documented list.
OBSERVED_EXTRA_TAGS: tuple[str, ...] = ("PARA", "MACR", "PAGE")

#: Bytes a MAP chunk needs per 16x16 cell: a 16-bit tile word plus one
#: collision byte (documented, and verified against all 104 sections).
MAP_BYTES_PER_CELL = 3

#: A CELL payload is a whole number of 64-byte 8x8 palettised cells.
CELL_BYTES = 8 * 8


def _read_u32(data: bytes, offset: int, endian: str) -> int | None:
    if offset + 4 > len(data):
        return None
    return struct.unpack(endian + "I", data[offset : offset + 4])[0]


@dataclass
class HeadRecord:
    """One HEAD block, interpreted under a stated hypothesis."""

    offset: int
    payload_size: int
    width_px: int | None
    height_px: int | None
    endian: str
    map_bytes: int | None = None
    expected_map_bytes: int | None = None
    map_ok: bool = False

    @property
    def tiles(self) -> tuple[int, int] | None:
        if not self.width_px or not self.height_px:
            return None
        return self.width_px // 16, self.height_px // 16


@dataclass
class WorldMeasurement:
    name: str
    size: int
    layout: str | None
    confidence: str
    tags: list[str]
    chunk_counts: dict[str, int]
    heads: list[HeadRecord]
    endian_votes: Counter = field(default_factory=Counter)
    gnmy: dict = field(default_factory=dict)
    cell: dict = field(default_factory=dict)

    @property
    def verified_heads(self) -> list[HeadRecord]:
        return [h for h in self.heads if h.map_ok]

    @property
    def width_histogram(self) -> Counter:
        return Counter(h.width_px for h in self.verified_heads if h.width_px)


def _following_map(chunks: list[Chunk], index: int) -> Chunk | None:
    """The MAP chunk that belongs to the HEAD at ``index`` (same quadruple)."""
    for follower in chunks[index + 1 : index + 5]:
        if follower.tag == "MAP":
            return follower
        if follower.tag == "HEAD":
            break
    return None


def read_heads(data: bytes, scan: ScanResult) -> list[HeadRecord]:
    """Interpret every HEAD chunk, validated against its MAP chunk.

    Documented: two ``u32`` values at the start of the payload, plane width and
    height in 8-pixel units, big-endian. Instead of guessing from the geometry,
    the decoded size is checked against the sibling MAP chunk: a 16x16 cell
    costs 3 bytes, and the payload is padded to a multiple of 4. A record whose
    MAP does not agree is reported with ``map_ok=False`` and excluded from
    histograms.
    """
    heads: list[HeadRecord] = []
    chunks = scan.chunks
    for index, chunk in enumerate(chunks):
        if chunk.tag != "HEAD":
            continue
        payload = data[chunk.payload_offset : chunk.payload_offset + chunk.payload_size]
        sibling = _following_map(chunks, index)
        map_bytes = sibling.payload_size if sibling else None
        for endian in (">", "<"):
            raw_w = _read_u32(payload, 0, endian)
            raw_h = _read_u32(payload, 4, endian)
            if not raw_w or not raw_h:
                heads.append(HeadRecord(chunk.payload_offset, chunk.payload_size, None, None, endian))
                continue
            width_px, height_px = raw_w * 8, raw_h * 8
            cells = (width_px // 16) * (height_px // 16)
            expected = cells * MAP_BYTES_PER_CELL
            ok = (
                map_bytes is not None
                and expected <= map_bytes <= expected + 3
                and map_bytes % 4 == 0
            )
            heads.append(
                HeadRecord(
                    offset=chunk.payload_offset,
                    payload_size=chunk.payload_size,
                    width_px=width_px,
                    height_px=height_px,
                    endian=endian,
                    map_bytes=map_bytes,
                    expected_map_bytes=expected,
                    map_ok=ok,
                )
            )
    return heads


def probe_gnmy(payload: bytes) -> dict:
    """Walk GNMY entries: ``u16`` size (LE) then a ``u16`` type, per entry.

    Observed layout, not yet confirmed against the engine: each entry is
    ``size`` bytes long, of which the first four are size and type, and the
    chunk ends with a few bytes that are not an entry. Type *names* live in NMY
    and the index-to-name mapping is **unverified**, so only indices are
    reported.
    """
    types: Counter = Counter()
    pos = 0
    entries = 0
    while pos + 2 <= len(payload):
        size = struct.unpack("<H", payload[pos : pos + 2])[0]
        if size < 4 or pos + size > len(payload):
            break
        types[struct.unpack("<H", payload[pos + 2 : pos + 4])[0]] += 1
        entries += 1
        pos += size
    return {
        "bytes": len(payload),
        "entries": entries,
        "trailing_bytes": len(payload) - pos,
        "distinct_types": len(types),
        "top_types": dict(types.most_common(10)),
    }


def measure_world(path: Path) -> WorldMeasurement:
    data = path.read_bytes()
    scan = scan_bytes(data, path=str(path))
    heads = read_heads(data, scan)
    votes: Counter = Counter()
    for head in heads:
        if head.map_ok:
            votes[head.endian] += 1

    gnmy_chunks = [c for c in scan.chunks if c.tag == "GNMY"]
    gnmy_totals: Counter = Counter()
    gnmy_entries = 0
    for c in gnmy_chunks:
        info = probe_gnmy(data[c.payload_offset : c.payload_offset + c.payload_size])
        gnmy_entries += info["entries"]
        gnmy_totals.update(info["top_types"])

    cell_sizes = [c.payload_size for c in scan.chunks if c.tag == "CELL"]
    anim_sizes = [c.payload_size for c in scan.chunks if c.tag == "ANIM"]

    return WorldMeasurement(
        name=path.name,
        size=len(data),
        layout=scan.layout,
        confidence=scan.confidence,
        tags=scan.tags,
        chunk_counts=dict(Counter(scan.tags)),
        heads=heads,
        endian_votes=votes,
        gnmy={
            "chunks": len(gnmy_chunks),
            "entries": gnmy_entries,
            "top_types": dict(gnmy_totals.most_common(10)),
        },
        cell={
            "chunks": len(cell_sizes),
            "bytes": sum(cell_sizes),
            "cells": sum(cell_sizes) // CELL_BYTES,
            "multiple_of_64": all(s % CELL_BYTES == 0 for s in cell_sizes),
        },
    )


@dataclass
class WavInfo:
    name: str
    size: int
    valid: bool
    channels: int | None = None
    rate: int | None = None
    bits: int | None = None
    data_bytes: int | None = None
    header_bytes: int | None = None
    magic: str = ""

    @property
    def seconds(self) -> float | None:
        if not (self.rate and self.channels and self.bits and self.data_bytes is not None):
            return None
        return self.data_bytes / (self.rate * self.channels * self.bits / 8)


def probe_wav(path: Path) -> WavInfo:
    """Parse a RIFF/WAVE header. Reports format only, never samples."""
    size = path.stat().st_size
    info = WavInfo(name=path.name, size=size, valid=False)
    with path.open("rb") as fh:
        head = fh.read(64)
    info.magic = head[:4].decode("ascii", "replace")
    if head[:4] != b"RIFF" or head[8:12] != b"WAVE":
        return info
    pos = 12
    fmt: tuple[int, int, int, int] | None = None  # channels, rate, bits, block
    while pos + 8 <= len(head):
        cid = head[pos : pos + 4]
        csize = struct.unpack("<I", head[pos + 4 : pos + 8])[0]
        body = pos + 8
        if cid == b"fmt " and body + 16 <= len(head):
            _tag, channels, rate, _brate, _align, bits = struct.unpack("<HHIIHH", head[body : body + 16])
            fmt = (channels, rate, bits, _align)
        elif cid == b"data":
            if fmt:
                info.channels, info.rate, info.bits, _ = fmt
                info.header_bytes = body
                # A data size that would overrun the file means the header is
                # not a plain streaming WAV; report the file size instead.
                info.data_bytes = min(csize, max(size - body, 0))
                info.valid = True
            return info
        pos = body + csize + (csize & 1)
    if fmt:
        info.channels, info.rate, info.bits, _ = fmt
    return info


def probe_audit_folder(folder: Path) -> list[WavInfo]:
    if not folder.is_dir():
        return []
    return [probe_wav(p) for p in sorted(folder.rglob("*")) if p.is_file()]


def probe_game_txt(path: Path) -> dict:
    """Structure of the localisation file: markers, lengths, encoding."""
    if not path.is_file():
        return {}
    raw = path.read_bytes()
    text = raw.decode("latin-1")  # never guess: report non-ASCII counts instead
    lines = text.splitlines()
    markers = {m: text.count(m) for m in ("@", "#", "&")}
    non_ascii = sum(1 for b in raw if b > 0x7E)
    return {
        "bytes": len(raw),
        "lines": len(lines),
        "markers": markers,
        "non_ascii_bytes": non_ascii,
        "longest_line": max((len(l) for l in lines), default=0),
        "lines_with_marker": sum(1 for l in lines if any(m in l for m in "@#&")),
    }


def probe_demos(folder: Path) -> dict:
    """Sizes and framing of the input recordings, no payload interpretation."""
    if not folder.is_dir():
        return {}
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    sizes = Counter(p.stat().st_size for p in files)
    sample = files[0].read_bytes()[:8] if files else b""
    printable = all(0x20 <= b < 0x7F for b in sample) if sample else False
    return {
        "files": len(files),
        "size_histogram": dict(sorted(sizes.items())),
        "first8_printable_ascii": printable,
        "extensions": sorted({p.suffix.lower() for p in files}),
    }


def measure_install(game_dir: str | Path) -> dict:
    """Collect every probe into one JSON-serialisable report."""
    root = Path(game_dir)
    entries = inventory(root)
    worlds = [measure_world(p) for p in find_world_files(root)]

    width_hist: Counter = Counter()
    height_hist: Counter = Counter()
    endian_votes: Counter = Counter()
    for w in worlds:
        for head in w.heads:
            if head.map_ok and head.width_px and head.height_px:
                width_hist[head.width_px] += 1
                height_hist[head.height_px] += 1
        endian_votes.update(w.endian_votes)

    audio: dict[str, list[WavInfo]] = {}
    for folder in ("SFX", "AMBIENT", "JINGLES"):
        audio[folder] = probe_audit_folder(root / folder)

    chunk_tags: Counter = Counter()
    for w in worlds:
        chunk_tags.update(w.tags)

    return {
        "game_dir": str(root),
        "install": [
            {"name": e.name, "present": e.present, "files": e.files, "bytes": e.bytes}
            for e in entries
        ],
        "worlds": [
            {
                "name": w.name,
                "size": w.size,
                "layout": w.layout,
                "confidence": w.confidence,
                "chunks": len(w.tags),
                "chunk_counts": w.chunk_counts,
                "planes": sum(1 for h in w.heads if h.endian == ">"),
                "planes_verified": len(w.verified_heads),
                "widths_px": sorted({h.width_px for h in w.verified_heads if h.width_px}),
                "heights_px": sorted({h.height_px for h in w.verified_heads if h.height_px}),
                "gnmy": w.gnmy,
                "cell": w.cell,
            }
            for w in worlds
        ],
        "world_totals": {
            "files": len(worlds),
            "bytes": sum(w.size for w in worlds),
            "planes": sum(1 for w in worlds for h in w.heads if h.endian == ">"),
            "planes_verified": sum(len(w.verified_heads) for w in worlds),
            "chunk_tags": dict(chunk_tags.most_common()),
            "undocumented_tags": sorted({t for t in chunk_tags if t not in KNOWN_TAGS}),
            "head_endian_votes": dict(endian_votes),
            "width_histogram_px": {str(k): v for k, v in sorted(width_hist.items())},
            "height_histogram_px": {str(k): v for k, v in sorted(height_hist.items())},
            "cells": sum(w.cell["cells"] for w in worlds),
            "cells_multiple_of_64": all(w.cell["multiple_of_64"] for w in worlds),
        },
        "audio": {
            folder: [
                {
                    "name": i.name,
                    "bytes": i.size,
                    "valid": i.valid,
                    "channels": i.channels,
                    "rate": i.rate,
                    "bits": i.bits,
                    "header_bytes": i.header_bytes,
                    "seconds": round(i.seconds, 2) if i.seconds else None,
                }
                for i in items
            ]
            for folder, items in audio.items()
        },
        "game_txt": probe_game_txt(root / "GAME.TXT"),
        "demos": probe_demos(root / "DEMOS"),
        "expected": {"files": list(EXPECTED_FILES), "dirs": list(EXPECTED_DIRS)},
    }


def summarise(report: dict) -> str:
    """Human-readable digest of :func:`measure_install`."""
    lines: list[str] = []
    totals = report["world_totals"]
    lines.append(f"install: {report['game_dir']}")
    lines.append(f"worlds:  {totals['files']} files, {totals['bytes']} bytes")
    lines.append(f"chunk tags seen: {', '.join(totals['chunk_tags'])}")
    if totals["undocumented_tags"]:
        lines.append(f"undocumented tags (not in the loader's list): {', '.join(totals['undocumented_tags'])}")
    lines.append(
        f"planes: {totals['planes']} ({totals['planes_verified']} verified against MAP size)"
    )
    lines.append(f"HEAD endian votes: {totals['head_endian_votes'] or 'none verified'}")
    lines.append(
        f"cells: {totals['cells']} x 64 B "
        f"({'all CELL payloads are whole cells' if totals['cells_multiple_of_64'] else 'MIXED sizes'})"
    )
    lines.append("")
    lines.append(f"{'world':<14}{'bytes':>9}{'chunks':>8}{'planes':>8}{'verif':>7}  widths (px)")
    for w in report["worlds"]:
        widths = ",".join(str(x) for x in w["widths_px"]) or "-"
        lines.append(
            f"{w['name']:<14}{w['size']:>9}{w['chunks']:>8}{w['planes']:>8}"
            f"{w['planes_verified']:>7}  {widths}"
        )

    hist = totals["width_histogram_px"]
    if hist:
        lines.append("")
        lines.append("plane-width histogram (planes, verified):")
        for width, count in hist.items():
            tiles = int(width) // 16
            bar = "#" * min(count, 60)
            lines.append(f"  {width:>5} px ({tiles:>3} tiles): {count:>3} {bar}")
    hh = totals["height_histogram_px"]
    if hh:
        lines.append("")
        lines.append("plane-height histogram: " + ", ".join(f"{k}px x{v}" for k, v in hh.items()))

    lines.append("")
    for folder, items in report["audio"].items():
        valid = [i for i in items if i["valid"]]
        formats = Counter((i["channels"], i["rate"], i["bits"]) for i in valid)
        total_s = sum(i["seconds"] or 0 for i in valid)
        lines.append(
            f"{folder}: {len(items)} files, {len(valid)} RIFF/WAVE, "
            f"{total_s:.1f}s total, formats {dict(formats)}"
        )

    gt = report["game_txt"]
    if gt:
        lines.append(
            f"GAME.TXT: {gt['bytes']} bytes, {gt['lines']} lines, markers {gt['markers']}, "
            f"non-ASCII {gt['non_ascii_bytes']}, longest {gt['longest_line']}"
        )
    demos = report["demos"]
    if demos:
        lines.append(
            f"DEMOS: {demos['files']} files, sizes {demos['size_histogram']}, "
            f"first8 printable={demos['first8_printable_ascii']}"
        )
    return "\n".join(lines)


def to_json(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True)
