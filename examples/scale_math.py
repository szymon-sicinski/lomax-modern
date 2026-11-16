#!/usr/bin/env python3
"""Reproduce the numbers quoted in docs/research/02-resolution.md.

No game files needed. Run:  python examples/scale_math.py
"""

from __future__ import annotations

HEIGHT = 240


def fade_surface(width: int) -> int:
    """Surface width the loader must allocate: a multiple of 32.

    The fade transition blits dissolve tiles across the screen, so the surface
    is rounded up to the next multiple of 32 (documented for 432 -> 448).
    """
    return -(-width // 32) * 32


def main() -> None:
    print("Widescreen candidates (height stays 240)")
    print(f"{'width':>6}{'aspect':>9}{'tiles':>7}{'surface':>9}  note")
    for w in (320, 336, 384, 432, 448, 480, 512, 560, 640):
        note = ""
        if w == 320:
            note = "original 4:3"
        elif w == 432:
            note = "16:9 preset"
        elif w == 512:
            note = "documented maximum"
        elif w == 560:
            note = "21:9, outside the cap"
        print(f"{w:>6}{w / HEIGHT:>9.3f}{w // 16:>7}{fade_surface(w):>9}  {note}")

    print()
    print("Presentation scaling (4:3 content)")
    for sw, sh in ((1366, 768), (1920, 1080), (1920, 1200), (2560, 1440), (3840, 2160)):
        fit_w = min(sw, int(sh * 4 / 3))
        fit_h = min(int(sw * 3 / 4), sh)
        print(f"  {sw}x{sh}: picture {fit_w}x{fit_h}, {fit_h / HEIGHT:.3f}x vertical")

    print()
    print("16:9 widescreen content (432x240)")
    for sw, sh in ((1920, 1080), (2560, 1440), (3840, 2160)):
        fit_h = int(sw / 1.8)
        print(f"  {sw}x{sh}: picture {sw}x{min(fit_h, sh)}")

    print()
    print("Internal render scale multipliers")
    for k in (2, 3, 4):
        print(
            f"  {k}x: {320 * k}x{HEIGHT * k} framebuffer, "
            f"{8 * k}x{8 * k} cells, {16 * k}x{16 * k} tiles"
        )


if __name__ == "__main__":
    main()
