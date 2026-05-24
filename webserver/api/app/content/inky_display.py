"""Server-side Inky Frame Spectra rendering.

The frame displays these PNGs with pngdec dithering disabled, so this module is
the final color quantizer for frame images.
"""

from __future__ import annotations

import io

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

STUCKI_DIVISOR = 42.0
STUCKI_CURRENT: tuple[tuple[int, int], ...] = ((1, 8), (2, 4))
STUCKI_NEXT: tuple[tuple[int, int], ...] = ((-2, 2), (-1, 4), (0, 8), (1, 4), (2, 2))
STUCKI_NEXT2: tuple[tuple[int, int], ...] = ((-2, 1), (-1, 2), (0, 4), (1, 2), (2, 1))


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


def _oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    return _linear_to_oklab(_srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b))


_PALETTE_OKLAB = tuple(_oklab(*color) for color in SPECTRA6_PALETTE)


def _closest_palette_color(r: float, g: float, b: float) -> tuple[int, int, int]:
    l, a, b_ = _oklab(r, g, b)
    best_index = 0
    best_distance = float("inf")
    for i, (pl, pa, pb) in enumerate(_PALETTE_OKLAB):
        dl = l - pl
        da = a - pa
        db = b_ - pb
        distance = dl * dl * 1.25 + da * da + db * db
        if distance < best_distance:
            best_distance = distance
            best_index = i
    return SPECTRA6_PALETTE[best_index]


def _clamp_channel(value: float) -> float:
    return max(0.0, min(255.0, value))


def _add_error(row: list[float], width: int, x: int, er: float, eg: float, eb: float, weight: float) -> None:
    if 0 <= x < width:
        i = x * 3
        row[i] += er * weight
        row[i + 1] += eg * weight
        row[i + 2] += eb * weight


def dither_image(img: Image.Image) -> Image.Image:
    """Return a six-color PNG-ready image using serpentine Stucki dithering."""
    rgb = img.convert("RGB")
    width, height = rgb.size
    out = Image.new("RGB", (width, height))
    src = rgb.load()
    dst = out.load()
    err_current = [0.0] * (width * 3)
    err_next = [0.0] * (width * 3)
    err_next2 = [0.0] * (width * 3)

    for y in range(height):
        direction = 1 if y % 2 == 0 else -1
        x_range = range(width) if direction == 1 else range(width - 1, -1, -1)
        for x in x_range:
            i = x * 3
            sr, sg, sb = src[x, y]
            r = _clamp_channel(sr + err_current[i])
            g = _clamp_channel(sg + err_current[i + 1])
            b = _clamp_channel(sb + err_current[i + 2])
            pr, pg, pb = _closest_palette_color(r, g, b)
            dst[x, y] = (pr, pg, pb)

            er = r - pr
            eg = g - pg
            eb = b - pb
            for offset, weight in STUCKI_CURRENT:
                _add_error(err_current, width, x + offset * direction, er, eg, eb, weight / STUCKI_DIVISOR)
            for offset, weight in STUCKI_NEXT:
                _add_error(err_next, width, x + offset * direction, er, eg, eb, weight / STUCKI_DIVISOR)
            for offset, weight in STUCKI_NEXT2:
                _add_error(err_next2, width, x + offset * direction, er, eg, eb, weight / STUCKI_DIVISOR)

        err_current = err_next
        err_next = err_next2
        err_next2 = [0.0] * (width * 3)
    return out


def apply_inky_display(image_bytes: bytes) -> bytes:
    """Return PNG bytes with final six-color Stucki dithering applied."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    processed = dither_image(img)
    buf = io.BytesIO()
    processed.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
