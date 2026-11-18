"""Structural probe for the ``ANIM`` / ``NMY`` / ``GNMY`` chunk payloads.

**Report, do not parse.**  For each of the three chunk types this module lists
the chunks it found (file, header/payload offsets, payload size) and then
scores a small set of *candidate record framings* by how cleanly each one
consumes the payload.  A framing is only ever labelled a hypothesis; no layout
is asserted and no payload is decoded into records, pixels or names.

The two framings that were previously documented as fact and have since been
contradicted by measurement are scored here and reported as ``retracted``:

* ``ANIM`` as an array of 0x38-byte ``SpriteFrame`` records ``[S2]``,
* ``NMY`` as a list of ``u16`` size + NUL-terminated name blocks ``[S2]``.

When no candidate consumes every chunk of a type exactly, that type is graded
``unresolved``.  The only data that leaves this module is offsets, sizes,
counts, coverage fractions and (for the single smallest ``ANIM`` chunk, to show
that it is a token stream rather than a header) its leading ``u16`` tokens.  No
game bytes are copied into the repository: everything below is computed at run
time against the user's own install.
"""

from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .doctor import find_world_files
from .wldscan import scan_bytes

#: The documented ``SpriteFrame`` record size that the ANIM falsification was
#: about.  ``0x38`` == 56 bytes.
ANIM_DOCUMENTED_RECORD_SIZE = 0x38

#: Number of leading ``u16`` tokens printed for the smallest ANIM chunk.  This
#: is a bounded structural diagnostic ("token stream, not a header"), not a
#: payload dump.
LEADING_TOKEN_COUNT = 8


@dataclass(frozen=True)
class ChunkRef:
    """One located chunk of a given tag."""

    file: str
    header_offset: int
    payload_offset: int
    payload_size: int


@dataclass
class Candidate:
    """One record-framing hypothesis and how far it got."""

    key: str
    label: str
    note: str
    status: str  # "hypothesis" | "retracted" | "consistent"
    chunks_consumed: int
    chunks_total: int
    bytes_consumed: int
    bytes_total: int

    @property
    def coverage(self) -> float:
        """Fraction of chunks whose payload the walker consumed exactly."""
        return self.chunks_consumed / self.chunks_total if self.chunks_total else 0.0


# ---------------------------------------------------------------------------
# Walkers.  Each returns ``(bytes_consumed, records_found)``.
# ---------------------------------------------------------------------------


def walk_fixed(payload: bytes, record_size: int) -> tuple[int, int]:
    """A bare array of fixed-size records: whole records only."""
    records = len(payload) // record_size if record_size else 0
    return records * record_size, records


def walk_u16_size(payload: bytes, endian: str, *, size_includes_field: bool) -> tuple[int, int]:
    """Records of a ``u16`` size followed by a body.

    ``size_includes_field`` decides whether the recorded size counts the
    2-byte size field itself (``total = size``) or only the body
    (``total = size + 2``).
    """
    pos, n, records = 0, len(payload), 0
    while pos + 2 <= n:
        size = struct.unpack(endian + "H", payload[pos : pos + 2])[0]
        total = size if size_includes_field else size + 2
        # A zero body size is degenerate (padding/terminator, not a record).
        if size == 0 or total < 2 or pos + total > n:
            break
        records += 1
        pos += total
    return pos, records


def walk_u32_size(payload: bytes, endian: str, *, size_includes_field: bool) -> tuple[int, int]:
    """Records of a ``u32`` size followed by a body."""
    pos, n, records = 0, len(payload), 0
    while pos + 4 <= n:
        size = struct.unpack(endian + "I", payload[pos : pos + 4])[0]
        total = size if size_includes_field else size + 4
        if size == 0 or total < 4 or pos + total > n:
            break
        records += 1
        pos += total
    return pos, records


def walk_u16_size_nul_name(payload: bytes) -> tuple[int, int]:
    """The documented NMY framing: ``u16`` size + a printable, NUL-terminated name.

    A record is accepted only when the ``size`` bytes after the field are all
    printable ASCII or NUL (i.e. they look like a name), which is the claim
    ``[S2]`` made.  The walk stops at the first byte that is not.
    """
    pos, n, records = 0, len(payload), 0
    while pos + 2 <= n:
        size = struct.unpack("<H", payload[pos : pos + 2])[0]
        if size == 0 or pos + 2 + size > n:
            break
        name = payload[pos + 2 : pos + 2 + size]
        if not all(b == 0 or 0x20 <= b < 0x7F for b in name):
            break
        records += 1
        pos += 2 + size
    return pos, records


def walk_gnmy(payload: bytes) -> tuple[int, int, int]:
    """The observed GNMY framing: ``u16`` size (LE) + ``u16`` type (LE).

    Returns ``(bytes_consumed, entries, trailing_bytes)``.  A chunk is
    considered *cleanly walked* when at least one entry was read and the
    leftover is the short terminator/pad (2 or 4 bytes) that the retail files
    end with.
    """
    pos, n, entries = 0, len(payload), 0
    while pos + 2 <= n:
        size = struct.unpack("<H", payload[pos : pos + 2])[0]
        if size < 4 or pos + size > n:
            break
        entries += 1
        pos += size
    return pos, entries, n - pos


# ---------------------------------------------------------------------------
# Hypothesis scoring.
# ---------------------------------------------------------------------------


def _candidate(
    key: str,
    label: str,
    note: str,
    payloads: list[bytes],
    walker,
    *,
    status: str = "hypothesis",
) -> Candidate:
    consumed_total = 0
    bytes_total = 0
    exact = 0
    for payload in payloads:
        consumed, _records = walker(payload)
        consumed_total += consumed
        bytes_total += len(payload)
        if consumed == len(payload):
            exact += 1
    return Candidate(
        key=key,
        label=label,
        note=note,
        status=status,
        chunks_consumed=exact,
        chunks_total=len(payloads),
        bytes_consumed=consumed_total,
        bytes_total=bytes_total,
    )


def _printable_runs(payload: bytes, min_len: int = 4) -> list[tuple[int, int]]:
    """(offset, length) of printable-ASCII runs of at least ``min_len`` chars."""
    runs: list[tuple[int, int]] = []
    i, n = 0, len(payload)
    while i < n:
        if 0x20 <= payload[i] < 0x7F:
            j = i
            while j < n and 0x20 <= payload[j] < 0x7F:
                j += 1
            if j - i >= min_len:
                runs.append((i, j - i))
            i = j
        else:
            i += 1
    return runs


def _probe_anim(chunks: list[ChunkRef], payloads: list[bytes]) -> dict:
    if not chunks:
        return {"tag": "ANIM", "chunks": 0, "bytes": 0, "size_min": None, "size_max": None,
                "all_multiple_of_4": True, "remainder_histogram_mod_0x38": {},
                "smallest": {}, "candidates": [], "verdict": "no chunks found"}

    sizes = [c.payload_size for c in chunks]
    remainder = Counter(s % ANIM_DOCUMENTED_RECORD_SIZE for s in sizes)

    smallest = min(chunks, key=lambda c: c.payload_size) if chunks else None
    smallest_info: dict = {}
    if smallest is not None:
        # Locate the payload bytes for the smallest chunk (payloads are in the
        # same order as ``chunks``).
        index = next(i for i, c in enumerate(chunks) if c is smallest)
        payload = payloads[index]
        tokens = [
            struct.unpack("<H", payload[i : i + 2])[0]
            for i in range(0, min(len(payload), LEADING_TOKEN_COUNT * 2), 2)
        ]
        smallest_info = {
            "file": smallest.file,
            "header_offset": smallest.header_offset,
            "payload_offset": smallest.payload_offset,
            "size": smallest.payload_size,
            "leading_u16_le": tokens,
        }

    candidates = [
        _candidate(
            "fixed-0x38",
            f"fixed {ANIM_DOCUMENTED_RECORD_SIZE}-byte (0x38) records [S2]",
            "a chunk that is a bare array of 0x38-byte records has a size that "
            "is a multiple of 0x38",
            payloads,
            lambda p: walk_fixed(p, ANIM_DOCUMENTED_RECORD_SIZE),
            status="retracted",
        ),
        _candidate("u16-size-le", "u16 size-prefixed records (LE, size = body)", "", payloads,
                   lambda p: walk_u16_size(p, "<", size_includes_field=False)),
        _candidate("u16-size-le-total", "u16 size-prefixed records (LE, size = total)", "", payloads,
                   lambda p: walk_u16_size(p, "<", size_includes_field=True)),
        _candidate("u16-size-be", "u16 size-prefixed records (BE, size = body)", "", payloads,
                   lambda p: walk_u16_size(p, ">", size_includes_field=False)),
        _candidate("u16-size-be-total", "u16 size-prefixed records (BE, size = total)", "", payloads,
                   lambda p: walk_u16_size(p, ">", size_includes_field=True)),
        _candidate("u32-size-le", "u32 size-prefixed records (LE, size = body)", "", payloads,
                   lambda p: walk_u32_size(p, "<", size_includes_field=False)),
        _candidate("u32-size-be", "u32 size-prefixed records (BE, size = body)", "", payloads,
                   lambda p: walk_u32_size(p, ">", size_includes_field=False)),
    ]

    any_winner = any(
        c.chunks_consumed == c.chunks_total and c.chunks_total > 0 and c.status != "retracted"
        for c in candidates
    )
    verdict = "consistent" if any_winner else "unresolved"

    return {
        "tag": "ANIM",
        "chunks": len(chunks),
        "bytes": sum(sizes),
        "size_min": min(sizes) if sizes else None,
        "size_max": max(sizes) if sizes else None,
        "all_multiple_of_4": all(s % 4 == 0 for s in sizes),
        "remainder_histogram_mod_0x38": {str(k): v for k, v in sorted(remainder.items())},
        "smallest": smallest_info,
        "candidates": [_candidate_dict(c) for c in candidates],
        "verdict": verdict,
    }


def _probe_nmy(chunks: list[ChunkRef], payloads: list[bytes]) -> dict:
    if not chunks:
        return {"tag": "NMY", "chunks": 0, "bytes": 0, "size_min": None, "size_max": None,
                "printable_runs_total": 0, "printable_runs_per_chunk_min": None,
                "printable_runs_per_chunk_max": None, "printable_run_length_histogram": {},
                "printable_runs_at_even_offset": 0, "candidates": [],
                "verdict": "no chunks found"}

    sizes = [c.payload_size for c in chunks]
    run_counts = [len(_printable_runs(p)) for p in payloads]
    run_lengths = Counter()
    even_offsets = 0
    total_runs = 0
    for p in payloads:
        for offset, length in _printable_runs(p):
            run_lengths[length] += 1
            total_runs += 1
            if offset % 2 == 0:
                even_offsets += 1

    candidates = [
        _candidate(
            "u16-size-nul-name",
            "u16 size + NUL-terminated name [S2]",
            "the documented NMY framing: a u16 size then that many bytes of "
            "printable/NUL name",
            payloads,
            walk_u16_size_nul_name,
            status="retracted",
        ),
        _candidate("u16-size-le", "u16 size-prefixed records (LE, size = body)", "", payloads,
                   lambda p: walk_u16_size(p, "<", size_includes_field=False)),
        _candidate("u16-size-be", "u16 size-prefixed records (BE, size = body)", "", payloads,
                   lambda p: walk_u16_size(p, ">", size_includes_field=False)),
    ]

    any_winner = any(
        c.chunks_consumed == c.chunks_total and c.chunks_total > 0 and c.status != "retracted"
        for c in candidates
    )
    verdict = "consistent" if any_winner else "unresolved"

    return {
        "tag": "NMY",
        "chunks": len(chunks),
        "bytes": sum(sizes),
        "size_min": min(sizes) if sizes else None,
        "size_max": max(sizes) if sizes else None,
        "printable_runs_total": total_runs,
        "printable_runs_per_chunk_min": min(run_counts) if run_counts else None,
        "printable_runs_per_chunk_max": max(run_counts) if run_counts else None,
        "printable_run_length_histogram": {str(k): v for k, v in sorted(run_lengths.items())},
        "printable_runs_at_even_offset": even_offsets,
        "candidates": [_candidate_dict(c) for c in candidates],
        "verdict": verdict,
    }


def _probe_gnmy(chunks: list[ChunkRef], payloads: list[bytes]) -> dict:
    if not chunks:
        return {"tag": "GNMY", "chunks": 0, "bytes": 0, "size_min": None, "size_max": None,
                "entries": 0, "trailing_bytes_histogram": {}, "candidates": [],
                "verdict": "no chunks found"}

    sizes = [c.payload_size for c in chunks]
    entries_total = 0
    trailing = Counter()
    clean = 0
    for p in payloads:
        _consumed, entries, leftover = walk_gnmy(p)
        entries_total += entries
        trailing[leftover] += 1
        if entries > 0 and leftover <= 4:
            clean += 1

    status = "consistent" if clean == len(payloads) else "hypothesis"
    candidate = Candidate(
        key="u16-size-u16-type",
        label="u16 size (LE) + u16 type (LE)",
        note="the observed GNMY placement framing: each entry is 'size' bytes "
        "long, the first four being size and type",
        status=status,
        chunks_consumed=clean,
        chunks_total=len(payloads),
        bytes_consumed=sum(p[0] for p in map(walk_gnmy, payloads)),
        bytes_total=sum(sizes),
    )

    return {
        "tag": "GNMY",
        "chunks": len(chunks),
        "bytes": sum(sizes),
        "size_min": min(sizes) if sizes else None,
        "size_max": max(sizes) if sizes else None,
        "entries": entries_total,
        "trailing_bytes_histogram": {str(k): v for k, v in sorted(trailing.items())},
        "candidates": [_candidate_dict(candidate)],
        # Structure is verified and recorded in file-formats.md §2.5; the
        # *meaning* of each type index is not, so the group is not "resolved".
        "verdict": (
            "structure-consistent (meaning unresolved)"
            if status == "consistent"
            else "unresolved"
        ),
    }


def _candidate_dict(c: Candidate) -> dict:
    return {
        "key": c.key,
        "label": c.label,
        "note": c.note,
        "status": c.status,
        "chunks_consumed": c.chunks_consumed,
        "chunks_total": c.chunks_total,
        "bytes_consumed": c.bytes_consumed,
        "bytes_total": c.bytes_total,
    }


# ---------------------------------------------------------------------------
# Collection and reporting.
# ---------------------------------------------------------------------------


def collect_chunks(game_dir: str | Path) -> tuple[dict[str, list[ChunkRef]], dict[str, list[bytes]]]:
    """Gather every ANIM/NMY/GNMY chunk from the world files, in file order."""
    refs: dict[str, list[ChunkRef]] = {"ANIM": [], "NMY": [], "GNMY": []}
    payloads: dict[str, list[bytes]] = {"ANIM": [], "NMY": [], "GNMY": []}
    for path in find_world_files(game_dir):
        data = path.read_bytes()
        scan = scan_bytes(data, path=path.name)
        for chunk in scan.chunks:
            if chunk.tag not in refs:
                continue
            refs[chunk.tag].append(
                ChunkRef(
                    file=path.name,
                    header_offset=chunk.header_offset,
                    payload_offset=chunk.payload_offset,
                    payload_size=chunk.payload_size,
                )
            )
            payloads[chunk.tag].append(
                data[chunk.payload_offset : chunk.payload_offset + chunk.payload_size]
            )
    return refs, payloads


def probe_anim_nmy(game_dir: str | Path) -> dict:
    """Run all three probes and return a JSON-serialisable report."""
    refs, payloads = collect_chunks(game_dir)
    return {
        "game_dir": str(Path(game_dir)),
        "groups": [
            _probe_anim(refs["ANIM"], payloads["ANIM"]),
            _probe_nmy(refs["NMY"], payloads["NMY"]),
            _probe_gnmy(refs["GNMY"], payloads["GNMY"]),
        ],
        "chunk_offsets": {
            tag: [
                {
                    "file": c.file,
                    "header_offset": c.header_offset,
                    "payload_offset": c.payload_offset,
                    "size": c.payload_size,
                }
                for c in refs[tag]
            ]
            for tag in ("ANIM", "NMY", "GNMY")
        },
    }


def format_report(report: dict) -> str:
    """Human-readable digest of :func:`probe_anim_nmy`.

    Every candidate framing is labelled a hypothesis (or ``retracted`` /
    ``consistent``) with its chunk-coverage score, and a group with no winner
    is printed as ``unresolved``.
    """
    lines: list[str] = [f"probe: ANIM / NMY / GNMY structural probe (report, not parse)"]
    lines.append(f"game_dir: {report['game_dir']}")
    lines.append("")

    for group in report["groups"]:
        tag = group["tag"]
        lines.append(f"== {tag}: {group['chunks']} chunks, {group['bytes']} bytes "
                     f"(sizes {group['size_min']}..{group['size_max']})")
        if tag == "ANIM":
            lines.append(
                "   all sizes multiple of 4: "
                f"{'yes' if group['all_multiple_of_4'] else 'no'}"
            )
            hist = group["remainder_histogram_mod_0x38"]
            lines.append(f"   size % 0x38 histogram: {hist}")
            small = group.get("smallest") or {}
            if small:
                tokens = small.get("leading_u16_le", [])
                lines.append(
                    f"   smallest chunk: {small.get('file')} @{small.get('payload_offset')}, "
                    f"{small.get('size')} B; leading u16 (LE) tokens: {tokens} "
                    "(token stream, not a header)"
                )
        if tag == "NMY":
            lines.append(
                f"   printable runs: {group['printable_runs_total']} total, "
                f"{group['printable_runs_per_chunk_min']}..{group['printable_runs_per_chunk_max']} "
                "per chunk; "
                f"{group['printable_runs_at_even_offset']} at even offsets; "
                f"lengths {group['printable_run_length_histogram']}"
            )
        if tag == "GNMY":
            lines.append(f"   entries: {group['entries']}")
            lines.append(f"   trailing bytes after last entry: {group['trailing_bytes_histogram']}")

        lines.append("   candidate framings (coverage = chunks fully consumed):")
        for c in group["candidates"]:
            status = c["status"]
            lines.append(
                f"     [{status:<10}] {c['label']:<52} "
                f"{c['chunks_consumed']}/{c['chunks_total']}"
            )
        lines.append(f"   verdict: {group['verdict']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
