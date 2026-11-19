/*
 * The M4 renderer core (C99) — implementation.  See renderer.h.
 */
#include "renderer.h"

uint16_t rgb15_to_rgb565(uint16_t word) {
    uint16_t red = (word >> 10) & 0x1Fu;
    uint16_t green = (word >> 5) & 0x1Fu;
    uint16_t blue = word & 0x1Fu;
    uint16_t green6 = (uint16_t)((green << 1) | (green >> 4));
    return (uint16_t)((red << 11) | (green6 << 5) | blue);
}

uint16_t rgb565_to_rgb15(uint16_t word) {
    uint16_t red = (word >> 11) & 0x1Fu;
    uint16_t green = (word >> 5) & 0x3Fu;
    uint16_t blue = word & 0x1Fu;
    return (uint16_t)((red << 10) | ((green >> 1) << 5) | blue);
}

int fade_surface_width(int width) {
    if (width < 0) {
        return -1;
    }
    /* ceil(width / 32) * 32, integer-only.  C division truncates toward zero,
     * so the Python floor-division form -(-w // 32) does not carry over;
     * (w + 31) / 32 is the same ceiling. */
    return ((width + 31) / 32) * 32;
}

void fb_init(framebuffer_t *fb, int width, int height, uint16_t fill) {
    int i;
    fb->width = width;
    fb->height = height;
    for (i = 0; i < width * height; i++) {
        fb->pixels[i] = fill;
    }
}

void fb_set(framebuffer_t *fb, int x, int y, uint16_t value) {
    if (x >= 0 && x < fb->width && y >= 0 && y < fb->height) {
        fb->pixels[y * fb->width + x] = value;
    }
}

void blit_cell(framebuffer_t *fb, const uint8_t *cell,
               const uint16_t *palette, int x0, int y0,
               uint16_t flip, uint8_t transparent) {
    int x, y;
    for (y = 0; y < 8; y++) {
        for (x = 0; x < 8; x++) {
            /* FLIP_H mirrors columns and FLIP_V rows: the decoder's axis
             * pairing ([H], Q33), identical to renderer.py's reference. */
            int sx = (flip & FLIP_H) ? (7 - x) : x;
            int sy = (flip & FLIP_V) ? (7 - y) : y;
            uint8_t index = cell[sy * 8 + sx];
            if (index == transparent) {
                continue;
            }
            fb_set(fb, x0 + x, y0 + y, palette[index]);
        }
    }
}

void blit_tile(framebuffer_t *fb, const uint16_t *record,
               const uint8_t *cells, int cell_count, const uint16_t *palette,
               int x0, int y0, int layout_2x2, uint8_t transparent) {
    int slot;
    for (slot = 0; slot < 4; slot++) {
        int index = (int)record[2 * slot];
        uint16_t flags = record[2 * slot + 1];
        int dx, dy;
        if (index < 0 || index >= cell_count) {
            continue;
        }
        if (layout_2x2) {
            /* column-major: slots 0/1 left column, 2/3 right */
            dx = (slot / 2) * 8;
            dy = (slot % 2) * 8;
        } else {
            dx = slot * 8;
            dy = 0;
        }
        blit_cell(fb, cells + index * 64, palette, x0 + dx, y0 + dy,
                  flags & (FLIP_H | FLIP_V), transparent);
    }
}
