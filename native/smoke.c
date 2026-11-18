/*
 * Headless smoke test for the M4 renderer core (C).
 *
 * Renders synthetic scenes and asserts the exact B5G6R5 words the Python
 * oracle (`tests/unit/test_renderer.py`) asserts, proving the C port
 * reproduces the reference bit-for-bit.  No game data, no display, no Wine:
 * this runs in CI under a plain ubuntu runner.
 *
 * Exit code 0 = all checks pass, 1 = a check failed.
 */
#include <stdio.h>
#include <string.h>

#include "renderer.h"

static int failures = 0;

#define CHECK(cond, msg)                                                        \
    do {                                                                        \
        if (cond) {                                                             \
            printf("  ok: %s\n", msg);                                          \
        } else {                                                                \
            printf("  FAIL: %s\n", msg);                                        \
            failures++;                                                         \
        }                                                                       \
    } while (0)

/* 15-bit source palette: index 0 transparent (magenta), 1 red, 2 green,
 * 3 blue, 4 white — the same fixture the Python golden test uses. */
static const uint16_t palette15[256] = {
    [0] = 0x7C1F, [1] = 0x7C00, [2] = 0x03E0, [3] = 0x001F, [4] = 0x7FFF,
};

/* The 8x8 scene: exercises white, red, green (5->6 expansion), blue and the
 * transparent key. */
static const uint8_t scene[64] = {
    4, 4, 4, 4, 4, 4, 4, 4,
    4, 0, 0, 0, 0, 0, 0, 4,
    4, 0, 1, 1, 1, 1, 0, 4,
    4, 0, 1, 2, 2, 1, 0, 4,
    4, 0, 1, 2, 3, 2, 0, 4,
    4, 0, 1, 1, 1, 1, 0, 4,
    4, 0, 0, 0, 0, 0, 0, 4,
    4, 4, 4, 4, 4, 4, 4, 4,
};

/* Hand-derived golden frame for `scene` over a black background. */
static const uint16_t golden[64] = {
    0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF,
    0xFFFF, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0xFFFF,
    0xFFFF, 0x0000, 0xF800, 0xF800, 0xF800, 0xF800, 0x0000, 0xFFFF,
    0xFFFF, 0x0000, 0xF800, 0x07E0, 0x07E0, 0xF800, 0x0000, 0xFFFF,
    0xFFFF, 0x0000, 0xF800, 0x07E0, 0x001F, 0x07E0, 0x0000, 0xFFFF,
    0xFFFF, 0x0000, 0xF800, 0xF800, 0xF800, 0xF800, 0x0000, 0xFFFF,
    0xFFFF, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0xFFFF,
    0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF,
};

static void test_palette_conversion(void) {
    printf("palette conversion (15-bit -> B5G6R5):\n");
    CHECK(rgb15_to_rgb565(0x7FFF) == 0xFFFF, "white widens to full white");
    CHECK(rgb15_to_rgb565(0x7C00) == 0xF800, "red passes 5->5");
    CHECK(rgb15_to_rgb565(0x03E0) == 0x07E0, "green 5->6 bit replication");
    CHECK(rgb15_to_rgb565(0x001F) == 0x001F, "blue passes 5->5");
    CHECK(rgb15_to_rgb565(0x0020) == 0x0040, "green 1 -> 2");
    CHECK(rgb565_to_rgb15(rgb15_to_rgb565(0x7C1F)) == 0x7C1F, "inverse round-trips");
}

static void test_fade_rule(void) {
    printf("fade-surface width rule (ceil(w/32)*32):\n");
    CHECK(fade_surface_width(0) == 0, "0 -> 0");
    CHECK(fade_surface_width(1) == 32, "1 -> 32");
    CHECK(fade_surface_width(32) == 32, "32 -> 32");
    CHECK(fade_surface_width(33) == 64, "33 -> 64");
    CHECK(fade_surface_width(320) == 320, "320 -> 320");
    CHECK(fade_surface_width(432) == 448, "432 -> 448");
    CHECK(fade_surface_width(560) == 576, "560 -> 576");
    CHECK(fade_surface_width(7201) == 7232, "7201 -> 7232");
    CHECK(fade_surface_width(-1) == -1, "negative -> -1");
}

static void test_cell_blit(void) {
    uint16_t palette[256];
    uint16_t pixels[64];
    framebuffer_t fb;
    int i;

    for (i = 0; i < 256; i++) {
        palette[i] = rgb15_to_rgb565(palette15[i]);
    }
    fb.pixels = pixels;
    fb_init(&fb, 8, 8, 0x0000);
    blit_cell(&fb, scene, palette, 0, 0, 0, 0);

    printf("cell blit (palette + transparency, golden frame):\n");
    CHECK(memcmp(pixels, golden, sizeof(golden)) == 0,
          "8x8 scene matches the hand-derived golden frame");
    CHECK(palette[0] == 0xF81F, "transparent key word is stored in the palette");
}

static void test_tile_blit(void) {
    uint16_t palette[256];
    uint8_t cells[4][64];
    uint16_t record[8] = {0, 0, 1, 0, 2, 0, 3, 0};
    uint16_t out_of_bank[8] = {0, 0, 99, 0, 1, 0, 2, 0};
    uint16_t pixels[32 * 8];
    uint16_t pixels16[16 * 16];
    framebuffer_t fb;
    int i;

    for (i = 0; i < 256; i++) {
        palette[i] = rgb15_to_rgb565(palette15[i]);
    }
    memset(cells, 0, sizeof(cells));
    for (i = 0; i < 64; i++) {
        cells[0][i] = 1; /* red */
        cells[1][i] = 2; /* green */
        cells[2][i] = 3; /* blue */
        cells[3][i] = 4; /* white */
    }

    printf("tile blit (four cells, stored order / 2x2):\n");
    fb.pixels = pixels;
    fb_init(&fb, 32, 8, 0x0000);
    blit_tile(&fb, record, &cells[0][0], 4, palette, 0, 0, 0, 0);
    CHECK(pixels[0] == 0xF800 && pixels[8] == 0x07E0 &&
              pixels[16] == 0x001F && pixels[24] == 0xFFFF,
          "strip places cells left-to-right in stored order");

    fb.pixels = pixels16;
    fb_init(&fb, 16, 16, 0x0000);
    blit_tile(&fb, record, &cells[0][0], 4, palette, 0, 0, 1, 0);
    CHECK(pixels16[0] == 0xF800 && pixels16[8] == 0x07E0 &&
              pixels16[8 * 16] == 0x001F && pixels16[8 * 16 + 8] == 0xFFFF,
          "2x2 assembles the 16x16 tile (cell order [H])");

    fb.pixels = pixels;
    fb_init(&fb, 32, 8, 0x0000);
    blit_tile(&fb, out_of_bank, &cells[0][0], 3, palette, 0, 0, 0, 0);
    CHECK(pixels[0] == 0xF800 && pixels[8] == 0x0000 && pixels[16] == 0x07E0,
          "out-of-bank index is skipped, not repaired");
}

static void test_tile_flip(void) {
    uint16_t palette[256];
    uint8_t corner[64];
    uint16_t pixels[8 * 8];
    framebuffer_t fb;
    int i;

    for (i = 0; i < 256; i++) {
        palette[i] = rgb15_to_rgb565(palette15[i]);
    }
    memset(corner, 0, sizeof(corner));
    corner[0] = 1; /* red, top-left only */

    printf("tile flip (H / V / both mirror the cell):\n");

    fb.pixels = pixels;
    fb_init(&fb, 8, 8, 0x0000);
    blit_cell(&fb, corner, palette, 0, 0, 0, 0);
    CHECK(pixels[0] == 0xF800 && pixels[7] == 0x0000,
          "unflipped: red stays top-left");

    fb_init(&fb, 8, 8, 0x0000);
    blit_cell(&fb, corner, palette, 0, 0, FLIP_H, 0);
    CHECK(pixels[7] == 0xF800 && pixels[0] == 0x0000,
          "H flip: red moves to top-right");

    fb_init(&fb, 8, 8, 0x0000);
    blit_cell(&fb, corner, palette, 0, 0, FLIP_V, 0);
    CHECK(pixels[7 * 8] == 0xF800 && pixels[0] == 0x0000,
          "V flip: red moves to bottom-left");

    fb_init(&fb, 8, 8, 0x0000);
    blit_cell(&fb, corner, palette, 0, 0, FLIP_H | FLIP_V, 0);
    CHECK(pixels[7 * 8 + 7] == 0xF800 && pixels[0] == 0x0000,
          "both: red moves to bottom-right");
}

int main(void) {
    test_palette_conversion();
    test_fade_rule();
    test_cell_blit();
    test_tile_blit();
    test_tile_flip();

    if (failures == 0) {
        printf("PASS: renderer smoke (all golden checks passed)\n");
        return 0;
    }
    printf("FAIL: %d check(s) failed\n", failures);
    return 1;
}
