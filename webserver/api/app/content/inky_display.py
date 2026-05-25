"""Server-side Inky Frame Spectra rendering.

The frame displays these PNGs with pngdec dithering disabled, so this module is
the final color quantizer for frame images.
"""

from __future__ import annotations

import io
from functools import lru_cache

from PIL import Image

# 7.3" Spectra: black, white, green, blue, red, yellow (no orange)
SPECTRA6_PALETTE: tuple[tuple[int, int, int], ...] = (
    (0, 0, 0),
    (255, 255, 255),
    (40, 130, 60),
    (35, 70, 160),
    (200, 30, 30),
    (240, 200, 40),
)

# Stucki error diffusion kernel: (weight, dx, dy). Scanned left-to-right only.
STUCKI_KERNEL: tuple[tuple[float, int, int], ...] = (
    (8 / 42, 1, 0),
    (4 / 42, 2, 0),
    (2 / 42, -2, 1),
    (4 / 42, -1, 1),
    (8 / 42, 0, 1),
    (4 / 42, 1, 1),
    (2 / 42, 2, 1),
    (1 / 42, -2, 2),
    (2 / 42, -1, 2),
    (4 / 42, 0, 2),
    (2 / 42, 1, 2),
    (1 / 42, 2, 2),
)


def _srgb_to_linear(channel: float) -> float:
    c = max(0.0, min(255.0, channel)) / 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _linear_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_ = l ** (1.0 / 3.0)
    m_ = m ** (1.0 / 3.0)
    s_ = s ** (1.0 / 3.0)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


@lru_cache(maxsize=65536)
def _oklab_rgb(r: int, g: int, b: int) -> tuple[float, float, float]:
    return _linear_to_oklab(_srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b))


_PALETTE_OKLAB = tuple(_oklab_rgb(*color) for color in SPECTRA6_PALETTE)


def _closest_palette_index(l: float, a: float, b: float) -> int:
    best_index = 0
    best_distance = float("inf")
    for i, (pl, pa, pb) in enumerate(_PALETTE_OKLAB):
        dl = l - pl
        da = a - pa
        db = b - pb
        distance = dl * dl + da * da + db * db
        if distance < best_distance:
            best_distance = distance
            best_index = i
    return best_index


def _add_error(
    err_l: list[float],
    err_a: list[float],
    err_b: list[float],
    width: int,
    height: int,
    x: int,
    y: int,
    el: float,
    ea: float,
    eb: float,
    weight: float,
) -> None:
    if 0 <= x < width and 0 <= y < height:
        i = y * width + x
        err_l[i] += el * weight
        err_a[i] += ea * weight
        err_b[i] += eb * weight


def dither_image(img: Image.Image) -> Image.Image:
    """Return a six-color PNG-ready image using OKLab Stucki dithering."""
    rgb = img.convert("RGB")
    width, height = rgb.size
    out = Image.new("RGB", (width, height))
    src = rgb.load()
    dst = out.load()
    pixel_count = width * height
    err_l = [0.0] * pixel_count
    err_a = [0.0] * pixel_count
    err_b = [0.0] * pixel_count

    for y in range(height):
        for x in range(width):
            i = y * width + x
            sr, sg, sb = src[x, y]
            pl_in, pa_in, pb_in = _oklab_rgb(sr, sg, sb)
            raw_l = pl_in + err_l[i]
            raw_a = pa_in + err_a[i]
            raw_b = pb_in + err_b[i]

            palette_index = _closest_palette_index(raw_l, raw_a, raw_b)
            pr, pg, pb = SPECTRA6_PALETTE[palette_index]
            dst[x, y] = (pr, pg, pb)

            chosen_l, chosen_a, chosen_b = _PALETTE_OKLAB[palette_index]
            error_l = raw_l - chosen_l
            error_a = raw_a - chosen_a
            error_b = raw_b - chosen_b
            for weight, dx, dy in STUCKI_KERNEL:
                _add_error(err_l, err_a, err_b, width, height, x + dx, y + dy, error_l, error_a, error_b, weight)
    return out


def apply_inky_display(image_bytes: bytes) -> bytes:
    """Return PNG bytes with final six-color Stucki dithering applied."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    processed = dither_image(img)
    buf = io.BytesIO()
    processed.save(buf, format="PNG", compress_level=6)
    return buf.getvalue()
