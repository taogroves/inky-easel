"""Inky Frame Spectra ordered dither preview (matches Pimoroni pngdec PNG_DITHER)."""

from __future__ import annotations

import io

from PIL import Image

from .renderer import INKY_PALETTE

# pimoroni/pimoroni-pico libraries/pico_graphics/pico_graphics.cpp
DITHER16_PATTERN: tuple[int, ...] = (0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5)

# 7.3" Spectra: black, white, green, blue, red, yellow (no orange)
SPECTRA6_PALETTE: tuple[tuple[int, int, int], ...] = (
    INKY_PALETTE["BLACK"],
    INKY_PALETTE["WHITE"],
    INKY_PALETTE["GREEN"],
    INKY_PALETTE["BLUE"],
    INKY_PALETTE["RED"],
    INKY_PALETTE["YELLOW"],
)

PALETTE_SIZE = len(SPECTRA6_PALETTE)


def _luminance(r: int, g: int, b: int) -> int:
    return r * 21 + g * 72 + b * 7


def _distance(r1: int, g1: int, b1: int, r2: int, g2: int, b2: int) -> int:
    rmean = (r1 + r2) // 2
    rx = r1 - r2
    gx = g1 - g2
    bx = b1 - b2
    return abs(((512 + rmean) * rx * rx) >> 8) + 4 * gx * gx + (((767 - rmean) * bx * bx) >> 8)


def _closest(r: int, g: int, b: int) -> int:
    best_i = 0
    best_d = 1 << 30
    for i in range(PALETTE_SIZE):
        pr, pg, pb = SPECTRA6_PALETTE[i]
        d = _distance(r, g, b, pr, pg, pb)
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


def _get_dither_candidates(r: int, g: int, b: int) -> list[int]:
    error = [0, 0, 0]
    candidates: list[int] = []
    for _ in range(16):
        cr = r + error[0]
        cg = g + error[1]
        cb = b + error[2]
        idx = _closest(cr, cg, cb)
        candidates.append(idx)
        pr, pg, pb = SPECTRA6_PALETTE[idx]
        error[0] += r - pr
        error[1] += g - pg
        error[2] += b - pb
    candidates.sort(key=lambda i: _luminance(*SPECTRA6_PALETTE[i]), reverse=True)
    return candidates


def _build_candidate_cache() -> list[list[int]]:
    cache: list[list[int]] = []
    for i in range(512):
        rr = (i & 0x1C0) >> 1
        gg = (i & 0x38) << 2
        bb = (i & 0x7) << 5
        r = rr | (rr >> 3) | (rr >> 6)
        g = gg | (gg >> 3) | (gg >> 6)
        b = bb | (bb >> 3) | (bb >> 6)
        cache.append(_get_dither_candidates(r, g, b))
    return cache


_CANDIDATE_CACHE = _build_candidate_cache()


def _cache_key(r: int, g: int, b: int) -> int:
    return ((r & 0xE0) << 1) | ((g & 0xE0) >> 2) | ((b & 0xE0) >> 5)


def dither_image(img: Image.Image) -> Image.Image:
    """Ordered dither using Pimoroni PicoGraphics_PenInky7::set_pixel_dither."""
    rgb = img.convert("RGB")
    width, height = rgb.size
    out = Image.new("RGB", (width, height))
    src = rgb.load()
    dst = out.load()
    for y in range(height):
        for x in range(width):
            r, g, b = src[x, y]
            key = _cache_key(r, g, b)
            pattern_index = (x & 3) | ((y & 3) << 2)
            palette_idx = _CANDIDATE_CACHE[key][DITHER16_PATTERN[pattern_index]]
            dst[x, y] = SPECTRA6_PALETTE[palette_idx]
    return out


def apply_inky_display(image_bytes: bytes) -> bytes:
    """Return PNG bytes with Inky Frame ordered dither applied."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    processed = dither_image(img)
    buf = io.BytesIO()
    processed.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
