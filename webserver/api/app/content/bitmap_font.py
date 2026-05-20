"""Pimoroni bitmap8 font (font8) for server-side rendering.

Glyph data from pimoroni/pimoroni-pico libraries/bitmap_fonts/font8_data.hpp
(MIT license, Pimoroni Ltd).
"""

from __future__ import annotations

from PIL import ImageDraw

FONT_HEIGHT = 8
FONT_MAX_WIDTH = 5
WIDTHS: tuple[int, ...] = (3, 1, 3, 5, 4, 4, 4, 1, 3, 3, 3, 3, 2, 3, 2, 4, 4, 3, 4, 4, 4, 4, 4, 4, 4, 4, 1, 2, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3, 4, 4, 4, 5, 4, 4, 4, 4, 4, 4, 5, 4, 4, 5, 4, 4, 4, 2, 4, 2, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 3, 4, 4, 3, 5, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 4, 4, 4, 3, 1, 3, 4)

GLYPH_DATA: tuple[int, ...] = (0, 0, 0, 0, 0, 95, 0, 0, 0, 0, 3, 0, 3, 0, 0, 40, 124, 40, 124, 40, 36, 122, 47, 18, 0, 102, 16, 8, 102, 0, 54, 73, 73, 124, 0, 3, 0, 0, 0, 0, 28, 34, 65, 0, 0, 65, 34, 28, 0, 0, 84, 56, 84, 0, 0, 16, 56, 16, 0, 0, 128, 96, 0, 0, 0, 16, 16, 16, 0, 0, 96, 96, 0, 0, 0, 96, 24, 6, 1, 0, 62, 65, 65, 62, 0, 66, 127, 64, 0, 0, 98, 81, 73, 70, 0, 33, 73, 77, 51, 0, 24, 22, 17, 127, 0, 79, 73, 73, 49, 0, 60, 74, 73, 48, 0, 1, 97, 25, 7, 0, 54, 73, 73, 54, 0, 6, 73, 41, 30, 0, 51, 0, 0, 0, 0, 128, 108, 0, 0, 0, 16, 40, 68, 0, 0, 40, 40, 40, 0, 0, 68, 40, 16, 0, 0, 2, 81, 9, 6, 0, 62, 73, 85, 94, 0, 126, 9, 9, 126, 0, 127, 73, 73, 54, 0, 62, 65, 65, 34, 0, 127, 65, 65, 62, 0, 127, 73, 73, 65, 0, 127, 9, 9, 1, 0, 62, 65, 73, 121, 0, 127, 8, 8, 127, 0, 65, 127, 65, 0, 0, 48, 64, 64, 63, 0, 127, 8, 20, 99, 0, 127, 64, 64, 64, 0, 127, 2, 4, 2, 127, 127, 2, 4, 127, 0, 62, 65, 65, 62, 0, 127, 9, 9, 6, 0, 62, 65, 33, 94, 0, 127, 9, 25, 102, 0, 70, 73, 73, 49, 0, 1, 1, 127, 1, 1, 63, 64, 64, 63, 0, 127, 64, 32, 31, 0, 63, 64, 32, 64, 63, 119, 8, 8, 119, 0, 71, 72, 72, 63, 0, 113, 73, 69, 67, 0, 127, 65, 0, 0, 0, 1, 6, 24, 96, 0, 65, 127, 0, 0, 0, 4, 2, 4, 0, 0, 64, 64, 64, 0, 0, 1, 1, 0, 0, 0, 32, 84, 84, 120, 0, 127, 68, 68, 56, 0, 56, 68, 68, 40, 0, 56, 68, 68, 127, 0, 56, 84, 84, 88, 0, 126, 9, 9, 2, 0, 24, 164, 164, 124, 0, 127, 4, 4, 120, 0, 4, 125, 64, 0, 0, 96, 128, 128, 125, 0, 127, 16, 40, 68, 0, 1, 127, 64, 0, 0, 124, 4, 120, 4, 120, 124, 4, 4, 120, 0, 56, 68, 68, 56, 0, 252, 36, 36, 24, 0, 24, 36, 36, 252, 0, 124, 8, 4, 4, 0, 72, 84, 84, 36, 0, 62, 68, 68, 32, 0, 60, 64, 64, 124, 0, 124, 64, 32, 28, 0, 60, 64, 32, 64, 60, 108, 16, 16, 108, 0, 28, 160, 160, 124, 0, 100, 84, 76, 0, 0, 8, 62, 65, 0, 0, 127, 0, 0, 0, 0, 65, 62, 8, 0, 0, 8, 4, 8, 4, 0)


def _glyph_index(ch: str) -> int | None:
    code = ord(ch)
    if 32 <= code <= 126:
        return code - 32
    return None


def _glyph_bytes(index: int) -> tuple[int, ...]:
    start = index * FONT_MAX_WIDTH
    return GLYPH_DATA[start : start + FONT_MAX_WIDTH]


def measure_text(text: str, scale: int = 1) -> int:
    width = 0
    for ch in text:
        idx = _glyph_index(ch)
        if idx is None:
            width += 4 * scale
            continue
        width += WIDTHS[idx] * scale
        if ch != " ":
            width += scale
    return width


def draw_text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    color,
    *,
    max_width: int | None = None,
    scale: int = 1,
) -> tuple[int, int]:
    """Draw bitmap8 text with optional word wrap. Returns (x, y) after last line."""
    if not text:
        return x, y
    lines: list[str] = []
    if max_width is None:
        lines = [text]
    else:
        words = text.replace("\n", " ").split()
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip() if line else word
            if measure_text(candidate, scale) <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                if measure_text(word, scale) > max_width:
                    chunk = ""
                    for ch in word:
                        test = chunk + ch
                        if measure_text(test, scale) <= max_width:
                            chunk = test
                        else:
                            if chunk:
                                lines.append(chunk)
                            chunk = ch
                    line = chunk
                else:
                    line = word
        if line:
            lines.append(line)

    cursor_x = x
    cursor_y = y
    line_height = FONT_HEIGHT * scale + scale
    for line in lines:
        cursor_x = x
        for ch in line:
            idx = _glyph_index(ch)
            if idx is None:
                cursor_x += 4 * scale
                continue
            gw = WIDTHS[idx]
            rows = _glyph_bytes(idx)
            for row_i, row_byte in enumerate(rows):
                for col_i in range(FONT_MAX_WIDTH):
                    if row_byte & (1 << (FONT_MAX_WIDTH - 1 - col_i)):
                        px = cursor_x + col_i * scale
                        py = cursor_y + row_i * scale
                        if scale == 1:
                            draw.point((px, py), fill=color)
                        else:
                            draw.rectangle(
                                (px, py, px + scale - 1, py + scale - 1),
                                fill=color,
                            )
            cursor_x += gw * scale
            if ch != " ":
                cursor_x += scale
        cursor_y += line_height
    return x, cursor_y
