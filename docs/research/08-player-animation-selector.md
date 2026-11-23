# 08. Player animation selector, pose timing and the `dx`/`dy` blit — evidence (AN1)

Slice **AN1** of
[`../roadmap/46-character-animation-plan.md`](../roadmap/46-character-animation-plan.md).
The findings live in [`../file-formats.md`](../file-formats.md) §2.6.2; this page
holds only **how to reproduce them**: the read-only disassembly commands for the
virtual addresses that carry a claim, and the audit script behind every
measured number. Nothing here is game data — the commands print instructions
from, and counts over, the user's own install, and no output is committed.

## 1. Disassembly (read-only)

Everything in §2.6.2 graded **[V]** was read with GNU `objdump` from binutils,
Intel syntax, and nothing was executed:

```bash
EXE="$LOMAX_GAME_DIR/LOMAX.EXE"
dis() { objdump -d -M intel --start-address="$1" --stop-address="$2" "$EXE" | tail -n +8; }

dis 0x411454 0x411469   # |vx| into esi (the value the selector compares)
dis 0x411F79 0x411FD0   # Q38: cmp esi,0x20000 / jg -> WALK (rate |vx|/0x700) or RUN (|vx|>>11)
dis 0x4116E8 0x4116F5   # air/ground split on state bit 0x1
dis 0x41193E 0x411C51   # air branch: JMP1/JMP2, FLO1/FLO2, vy -> pose byte
dis 0x4106DE 0x410710   # jump launch: moving -> lockout 5, bit 0x2 cleared; standing -> 10, set
dis 0x410E96 0x410EC8   # touchdown: landing counter 10 only after a bit-0x2 jump
dis 0x411D2D 0x411D6B   # LND1 while the counter runs
dis 0x411E3D 0x411F1B   # idle: frozen STA1, then STA1/STA2 once
dis 0x416110 0x416230   # set-clip-if-different, set-clip, advance, pose->keyframe
dis 0x4160E0 0x416105   # pose count = keyframes with flag 0x80
dis 0x40C600 0x40C72A   # blit: frame address, mirroring, vertical clip (top = origin y + dy)
dis 0x40CD39 0x40CE78   # step-0 keyframe -> callback; loop ends on flag 0x80
dis 0x40C86E 0x40C87C   # prepend to the depth bucket
dis 0x404DAB 0x404E0B   # renderer walks each bucket head-first
dis 0x415FC8 0x416001   # the neg at 0x415FF9: a GDI DIB height, not dx/dy
dis 0x404C5B 0x404CA1   # catch-up loop: player routine 0x40FB70 once per tick
```

Quote at most the single instruction that carries a claim; never paste the
listing into the repository, an issue or a PR body.

## 2. Measurements over the retail `NMY` data

Save the script below **outside the repository**, then:

```bash
python3 -m pip install --user -e .          # from the repo root
export PYTHONPATH="$PWD/src"
python3 /path/outside/repo/an1_audit.py hero    "$LOMAX_GAME_DIR"   # rate, poses, bottom row per Hero clip
python3 /path/outside/repo/an1_audit.py anchor  "$LOMAX_GAME_DIR"   # top/bottom rows under the blit's placement
python3 /path/outside/repo/an1_audit.py overrun "$LOMAX_GAME_DIR"   # 0 of 4,788 drawn keyframes overrun
python3 /path/outside/repo/an1_audit.py step0   "$LOMAX_GAME_DIR"   # unresolved bytes sit only on step 0
```

Output on the author's install (`main` = `0523602`, 2026-11-23):

* `overrun` → `drawn keyframes with a resolvable sprite: 4788; step > own chunk
  frame_count: 0; clips affected: 0/691`.
* `step0` → step-0 keyframes by sprite byte `{100: 1, 106: 1, 169: 34, 222: 1,
  236: 8, 240: 5, 242: 3, 244: 6, 247: 1, 248: 2, 249: 1, 254: 12, 255: 19}`
  (94 keyframes); `unresolved sprite bytes on step>0 keyframes: {}`.
* `anchor` → `WALK` top −47…−43, bottom 0; `RUN` top −42…−34 (spread 8),
  bottom −7…0, bottom-pinned spread 9; `STA1` bottom 0; `JMP1` bottom −18…0;
  `JMP2` −16…0; `LND1` 0; `FLO1` 6; `FLO2` 5.
* `hero` → rate 64 in 24 of the 47 clips; `WALK` 72, `RUN` 90, `STA2` 68,
  `JPAD` 186 (highest), `BUI2` 33 (lowest); `WALK` 10 poses, `RUN` 12, `STA1`
  30, `STA2` 76, `JMP1`/`JMP2` 7, `LND1` 1, `FLO1`/`FLO2` 5; bottom row
  exactly 0 in every pose of 16 clips (`WALK`, `STA1`, `STA2`, `THR2`, `DUCK`,
  `BRAK`, `PUSH`, `LND1`, `EDGE`, `WAHL`, `DIZZ`, `DIG1`, `IN`, `OUT`, `HEL5`,
  `HEL8`).

```python
"""an1_audit.py -- reproduce the AN1 measurements (docs/file-formats.md s2.6.2).

Run OUTSIDE the repository, read-only:
    PYTHONPATH=src python3 an1_audit.py <subcommand> "$LOMAX_GAME_DIR"
Subcommands: hero | anchor | overrun | step0
Prints counts, sizes, offsets and clip parameters only -- never pixels or file bytes.
"""
import struct
import sys
from collections import Counter
from pathlib import Path

from lomax_modern import anim_nmy, wld
from lomax_modern.anim_clip import chunk_index_for_sprite, sprite_map


def clips_with_params(payload):
    """Walk the NMY framing (as anim_nmy.decode_nmy) but keep the 9 u16 fields."""
    pos = 0
    count0 = struct.unpack_from("<H", payload, pos)[0]
    pos += 2
    out = []
    while count0:
        nul = payload.find(b"\x00", pos)
        name = payload[pos:nul].decode("ascii", "replace")
        pos += (count0 >> 1) * 2
        _wa, wb = struct.unpack_from("<HH", payload, pos)
        pos += 6
        for _ in range(wb):
            tag = struct.unpack_from("<I", payload, pos)[0]
            n = struct.unpack_from("<H", payload, pos + 8)[0]
            params = struct.unpack_from("<9H", payload, pos + 10)  # params[0] = rate (VA 0x41527E)
            kfs = [struct.unpack_from("<BBhhH", payload, pos + 28 + 8 * i) for i in range(n)]
            out.append((name, anim_nmy.anim_tag_name(tag).strip(), params, kfs))
            pos += 28 + 8 * n
        count0 = struct.unpack_from("<H", payload, pos)[0]
        pos += 2
    return out


def world(path):
    w = wld.parse_file(path)
    chunk = next(c for c in w.chunks if c.tag == "NMY")
    return w, clips_with_params(chunk.payload)


def poses(kfs):
    """A pose ends at the keyframe whose flag word has 0x80 (VA 0x4160E0, 0x40CE68)."""
    out, cur = [], []
    for k in kfs:
        cur.append(k)
        if k[4] & 0x80:
            out.append(cur)
            cur = []
    return out, cur


def body_frame(sm, k):
    return sm[chunk_index_for_sprite(k[0])].frames[k[1] - 1]


def hero(game):
    w, clips = world(game / "WORLDS" / "MAIN.WLD")
    sm = sprite_map(w)
    print("| tag | rate (/256 poses per tick) | ticks/pose | keyframes | poses | "
          "last-drawn layer's bottom row dy+h-1 | step-0 (sprite, flags&7) |")
    for name, tag, params, kfs in clips:
        if name != "Hero":
            continue
        ps, tail = poses(kfs)
        rate = params[0]
        tpp = f"{256 / rate:.2f}" if rate else "frozen"
        bots = []
        for p in ps:
            drawn = [k for k in p if k[0] and k[1]]
            if drawn:  # the pose's last drawn keyframe is painted first (the body in Hero's clips)
                bots.append(drawn[-1][3] + abs(body_frame(sm, drawn[-1]).height) - 1)
        rng = f"{min(bots)}" if min(bots) == max(bots) else f"{min(bots)}..{max(bots)}"
        s0 = sorted({(k[0], k[4] & 7) for k in kfs if k[0] and k[1] == 0})
        print(f"| {tag} | {rate} | {tpp} | {len(kfs)} | {len(ps)}{' +tail' if tail else ''} | {rng} | {s0 or '-'} |")


def anchor(game):
    """Body top row (dy) and bottom row (dy + h - 1) under the blit's placement:
    layer top-left = origin + (dx, dy), screen y down (VA 0x40C6F0-0x40C71E)."""
    w, clips = world(game / "WORLDS" / "MAIN.WLD")
    sm = sprite_map(w)
    for name, tag, _params, kfs in clips:
        if name != "Hero" or tag not in ("WALK", "RUN", "STA1", "JMP1", "JMP2", "LND1", "FLO1", "FLO2"):
            continue
        ps, _ = poses(kfs)
        tops, bots, hs = [], [], []
        for p in ps:
            body = next(k for k in reversed(p) if k[0] and k[1])  # last drawn keyframe = the body
            h = abs(body_frame(sm, body).height)
            tops.append(body[3])
            bots.append(body[3] + h - 1)
            hs.append(h)
        print(f"{tag}: poses {len(ps)}; body top dy {min(tops)}..{max(tops)} (spread {max(tops) - min(tops)}); "
              f"bottom row {min(bots)}..{max(bots)}; bottom-pinned top spread {max(hs) - min(hs)}")


def overrun(game):
    """Does any drawn keyframe's step exceed ITS OWN sprite's frame count?"""
    total = over = clips_over = clips = 0
    for p in sorted((game / "WORLDS").glob("*.WLD")):
        w, cl = world(p)
        sm = sprite_map(w)
        for _name, _tag, _params, kfs in cl:
            clips += 1
            bad = 0
            for k in kfs:
                if k[0] == 0 or k[1] == 0 or chunk_index_for_sprite(k[0]) not in sm:
                    continue
                total += 1
                bad += k[1] > sm[chunk_index_for_sprite(k[0])].frame_count
            over += bad
            clips_over += bool(bad)
    print(f"drawn keyframes with a resolvable sprite: {total}; step > own chunk frame_count: {over}; "
          f"clips affected: {clips_over}/{clips}")


def step0(game):
    """Which sprite bytes sit on step-0 keyframes (never blitted: VA 0x40CD39)."""
    s0, unresolved_drawn = Counter(), Counter()
    for p in sorted((game / "WORLDS").glob("*.WLD")):
        w, cl = world(p)
        sm = sprite_map(w)
        for _name, _tag, _params, kfs in cl:
            for k in kfs:
                if k[0] and k[1] == 0:
                    s0[k[0]] += 1
                elif k[0] and chunk_index_for_sprite(k[0]) not in sm:
                    unresolved_drawn[(p.stem, k[0])] += 1
    print("step-0 keyframes by sprite byte:", dict(sorted(s0.items())), "total", sum(s0.values()))
    print("unresolved sprite bytes on step>0 keyframes:", dict(sorted(unresolved_drawn.items())))


if __name__ == "__main__":
    {"hero": hero, "anchor": anchor, "overrun": overrun, "step0": step0}[sys.argv[1]](Path(sys.argv[2]))
```
