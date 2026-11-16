"""Read-only measurement probes for a Lomax installation.

Every number this module reports is either read straight from a file header or
explicitly labelled as a hypothesis. It never writes to the game folder and
never copies asset bytes: sizes, counts, offsets and header fields only.

The goal is the Phase 0 measurement set from
``docs/research/04-improvement-backlog.md`` (LMX-1, LMX-2) and the format
questions in ``docs/research/05-open-questions.md``:

* which chunk sequence the world files actually use,
* how many level sections (HEAD blocks) each world holds,
* the distribution of plane widths — the number that decides whether anything
  wider than 512x240 is worth pursuing,
* the audio formats inside ``SFX``/``AMBIENT``/``JINGLES``,
* the shape of ``DEMOS/*.DAT`` and ``GAME.TXT``.
"""

from __future__ import annotations

import json
import struct
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .doctor import EXPECTED_DIRS, EXPECTED_FILES, find_world_files, inventory
from .wldscan import KNOWN_TAGS, ScanResult, scan_bytes

#: Tags seen in real files but absent from the documented set. Kept here so the
#: scanner can be widened without losing the "is this documented?" distinction.
OBSERVED_EXTRA_TAGS: tuple[str, ...] = ("PARA", "MACR", "PAGE")

#: Plausible plane geometries, in pixels, for validating a HEAD hypothesis.
_PLAUSIBLE_HEIGHTS = (192, 224, 240, 256, 480, 512)
_MIN_WIDTH, _MAX_WIDTH = 160, 4096


@dataclass
class HeadRecord:
    """One HEAD block, interpreted under a stated hypothesis."""

    offset: int
    payload_size: int
    width_px: int | None
    height_px: int | None
    endian: str
    plausible: bool


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

    @property
    def width_histogram(self) -> Counter:
        return Counter(h.width_px for h in self.heads if h.width_px)


def _read_u32(data: bytes, offset: int, endian: str) -> int | None:
    if offset + 4 > len(data):
        return None
    return struct.unpack(endian + "I", data[offset : offset + 4])[0]


def read_heads(data: bytes, scan: ScanResult) -> list[HeadRecord]:
    """Interpret every HEAD chunk under the documented layout.

    Documented (not yet verified): two ``u32`` values at the start of the
    payload, plane width and height, in 8-pixel units, big-endian. We evaluate
    both endiannesses and mark a record plausible only when the decoded geometry
    lands in a sane range and the height matches a known screen height.
    """
    heads: list[HeadRecord] = []
    for chunk in scan.chunks:
        if chunk.tag != "HEAD":
            continue
        payload = data[chunk.payload_offset : chunk.payload_offset + chunk.payload_size]
        for endian in (">", "<"):
            raw_w = _read_u32(payload, 0, endian)
            raw_h = _read_u32(payload, 4, endian)
            if raw_w is None or raw_h is None:
                heads.append(HeadRecord(chunk.payload_offset, chunk.payload_size, None, None, endian, False))
                continue
            width_px, height_px = raw_w * 8, raw_h * 8
            plausible = (
                _MIN_WIDTH <= width_px <= _MAX_WIDTH
                and height_px in _PLAUSIBLE_HEIGHTS
                and raw_w % 2 == 0
                and width_px % 16 == 0
            )
            heads.append(
                HeadRecord(
                    offset=chunk.payload_offset,
                    payload_size=chunk.payload_size,
                    width_px=width_px,
                    height_px=height_px,
                    endian=endian,
                    plausible=plausible,
                )
            )
    return heads


def measure_world(path: Path) -> WorldMeasurement:
    data = path.read_bytes()
    scan = scan_bytes(data, path=str(path))
    heads = read_heads(data, scan)
    votes: Counter = Counter()
    for head in heads:
        if head.plausible:
            votes[head.endian] += 1
    return WorldMeasurement(
        name=path.name,
        size=len(data),
        layout=scan.layout,
        confidence=scan.confidence,
        tags=scan.tags,
        chunk_counts=dict(Counter(scan.tags)),
        heads=heads,
        endian_votes=votes,
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
    worlds = find_world_files(root)
    world_results = [measure_world(p) for p in worlds]

    width_hist: Counter = Counter()
    endian_votes: Counter = Counter()
    for w in world_results:
        for head in w.heads:
            if head.plausible and head.width_px:
                width_hist[head.width_px] += 1
        endian_votes.update(w.endian_votes)

    audio: dict[str, list[WavInfo]] = {}
    for folder in ("SFX", "AMBIENT", "JINGLES"):
        audio[folder] = probe_audit_folder(root / folder)

    chunk_tags: Counter = Counter()
    for w in world_results:
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
                "heads": len(w.heads) // 2,  # two endianness interpretations each
                "widths_px": sorted({h.width_px for h in w.heads if h.plausible and h.width_px}),
                "heights_px": sorted({h.height_px for h in w.heads if h.plausible and h.height_px}),
            }
            for w in world_results
        ],
        "world_totals": {
            "files": len(world_results),
            "bytes": sum(w.size for w in world_results),
            "chunk_tags": dict(chunk_tags.most_common()),
            "undocumented_tags": sorted({t for t in chunk_tags if t not in KNOWN_TAGS}),
            "head_endian_votes": dict(endian_votes),
            "width_histogram_px": {str(k): v for k, v in sorted(width_hist.items())},
            "width_histogram_tiles": {
                str(k // 16): v for k, v in sorted(width_hist.items())
            },
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
        lines.append(f"undocumented tags: {', '.join(totals['undocumented_tags'])}")
    lines.append(f"HEAD endian votes: {totals['head_endian_votes'] or 'none plausible'}")
    lines.append("")
    lines.append(f"{'world':<14}{'bytes':>9}{'chunks':>8}{'heads':>7}  widths (px)")
    for w in report["worlds"]:
        widths = ",".join(str(x) for x in w["widths_px"]) or "-"
        lines.append(f"{w['name']:<14}{w['size']:>9}{w['chunks']:>8}{w['heads']:>7}  {widths}")

    hist = totals["width_histogram_px"]
    if hist:
        lines.append("")
        lines.append("plane-width histogram (sections):")
        for width, count in hist.items():
            tiles = int(width) // 16
            bar = "#" * min(count, 60)
            lines.append(f"  {width:>5} px ({tiles:>3} tiles): {count:>3} {bar}")

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
