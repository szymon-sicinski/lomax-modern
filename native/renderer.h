/*
 * The M4 renderer core (C99): 16-bit B5G6R5 framebuffer, palette, blit.
 *
 * This is the hot-path port of `src/lomax_modern/renderer.py`, which is the
 * reference implementation and test oracle.  These functions reproduce the
 * Python rules bit-for-bit and `smoke.c` asserts the same golden B5G6R5 words
 * that `tests/unit/test_renderer.py` asserts.
 *
 * Built in CI only (`make -C native`), never at `pip install` time: the Python
 * package has no compiler dependency (see `docs/architecture.md` §5).
 *
 * Clean-room: this code reads no game data and interprets nothing beyond the
 * measured layout in `docs/file-formats.md`.  See the module docstring of
 * `renderer.py` for the confidence labels (V/H) behind each rule.
 */
#ifndef LOMAX_RENDERER_H
#define LOMAX_RENDERER_H

#include <stdint.h>

/* A mutable 16-bit B5G6R5 framebuffer, row-major. */
typedef struct {
    int width;
    int height;
    uint16_t *pixels; /* width * height words, caller-allocated */
} framebuffer_t;

/* Flip bits of a TTAB *flag* word (bits 13-14): mirror a cell about its axis. */
#define FLIP_H 0x2000u /* horizontal flip */
#define FLIP_V 0x4000u /* vertical flip */

/* Widen a 15-bit little-endian colour (blue 0-4, green 5-9, red 10-14) to
 * B5G6R5.  Green widens 5->6 by bit replication, the round-trip-preserving
 * expansion ([H], see renderer.py). */
uint16_t rgb15_to_rgb565(uint16_t word);

/* Inverse of rgb15_to_rgb565: narrow B5G6R5 back to 15-bit. */
uint16_t rgb565_to_rgb15(uint16_t word);

/* Round a surface width up to a multiple of 32 (ceil(w/32)*32), the
 * fade/dissolve-surface rule (docs/research/02-resolution.md §2.4).
 * Returns -1 for a negative width. */
int fade_surface_width(int width);

/* Fill a framebuffer with `fill` (caller owns `fb->pixels`). */
void fb_init(framebuffer_t *fb, int width, int height, uint16_t fill);

/* Set one pixel, clipping silently (a tile blitted partly off-screen clips). */
void fb_set(framebuffer_t *fb, int x, int y, uint16_t value);

/* Draw one 8x8 cell (64 palette indices, row-major) at (x0, y0); the
 * transparent index is skipped, leaving the destination untouched.  `flip`
 * is FLIP_H/FLIP_V (or both) and mirrors the cell about its own axis. */
void blit_cell(framebuffer_t *fb, const uint8_t *cell,
               const uint16_t *palette, int x0, int y0,
               uint16_t flip, uint8_t transparent);

/* Draw a TTAB record (16 bytes = four [index, flag] cells) as four 8x8
 * cells.  `record` is 8 u16 words: for slot 0..3, index = record[2*slot],
 * flags = record[2*slot+1].  `cells` is a flat bank of `cell_count` cells,
 * 64 bytes each.  `layout_2x2` selects the documented 16x16 2x2 assembly
 * ([H]) over the stored-order strip.  Each cell honours its flag word's flip;
 * an index outside the bank is skipped, never repaired. */
void blit_tile(framebuffer_t *fb, const uint16_t *record,
               const uint8_t *cells, int cell_count, const uint16_t *palette,
               int x0, int y0, int layout_2x2, uint8_t transparent);

#endif /* LOMAX_RENDERER_H */
