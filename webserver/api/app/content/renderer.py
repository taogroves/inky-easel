"""Pillow-backed renderers that produce JPEG payloads sized for an Inky Frame.

The frame decodes JPEGs via `jpegdec`, which orders-dithers to its palette.
We keep our palette close to the native Inky colours so the dithering looks
clean. Fonts: we use the default Pillow truetype lookup; if the platform has
DejaVu (most Debian/Ubuntu containers do, including python:3.12-slim once we
install fonts-dejavu-core) we use that.
"""

from __future__ import annotations

import io
import textwrap
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps

INKY_PALETTE = {
    "BLACK": (0, 0, 0),
    "WHITE": (255, 255, 255),
    "GREEN": (40, 130, 60),
    "BLUE": (35, 70, 160),
    "RED": (200, 30, 30),
    "YELLOW": (240, 200, 40),
    "ORANGE": (235, 120, 30),
}

DISPLAY_DIMENSIONS = {
    "inky_frame_4": (640, 400),
    "inky_frame_5_7": (600, 448),
    "inky_frame_7": (800, 480),
    "inky_frame_7_spectra": (800, 480),
}


@dataclass
class RenderTarget:
    width: int
    height: int


def target_for(display_type: str) -> RenderTarget:
    w, h = DISPLAY_DIMENSIONS.get(display_type, (800, 480))
    return RenderTarget(w, h)


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split(" ")
        line = ""
        for word in words:
            candidate = (line + " " + word).strip() if line else word
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                if draw.textbbox((0, 0), word, font=font)[2] > max_width:
                    chars = textwrap.wrap(word, width=max(8, max_width // (font.size // 2 or 1)))
                    lines.extend(chars[:-1])
                    line = chars[-1] if chars else ""
                else:
                    line = word
        if line:
            lines.append(line)
    return lines


def _to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()


def _new_canvas(target: RenderTarget, background: str = "WHITE") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (target.width, target.height), INKY_PALETTE[background])
    return img, ImageDraw.Draw(img)


def fit_image_to_target(image_bytes: bytes, target: RenderTarget) -> Image.Image:
    inbound = Image.open(io.BytesIO(image_bytes))
    inbound = ImageOps.exif_transpose(inbound)
    if inbound.mode in {"RGBA", "LA"} or (inbound.mode == "P" and "transparency" in inbound.info):
        transparent = inbound.convert("RGBA")
        background = Image.new("RGBA", transparent.size, INKY_PALETTE["WHITE"] + (255,))
        background.alpha_composite(transparent)
        inbound = background.convert("RGB")
    else:
        inbound = inbound.convert("RGB")

    inbound.thumbnail((target.width, target.height), Image.LANCZOS)

    img = Image.new("RGB", (target.width, target.height), INKY_PALETTE["WHITE"])
    ox = (target.width - inbound.width) // 2
    oy = (target.height - inbound.height) // 2
    img.paste(inbound, (ox, oy))
    return img


def prepare_inbox_image(image_bytes: bytes, target: RenderTarget) -> bytes:
    return _to_jpeg(fit_image_to_target(image_bytes, target))


def render_title_body(target: RenderTarget, title: str, body: str, accent: str = "BLUE",
                       footer: str | None = None) -> bytes:
    img, draw = _new_canvas(target)

    bar_h = max(56, target.height // 9)
    draw.rectangle((0, 0, target.width, bar_h), fill=INKY_PALETTE.get(accent, INKY_PALETTE["BLUE"]))

    title_font = _load_font(34, bold=True)
    draw.text((20, (bar_h - 34) // 2), title or "", fill=INKY_PALETTE["WHITE"], font=title_font)

    body_font = _load_font(22)
    lines = _wrap(draw, body or "", body_font, target.width - 60)

    y = bar_h + 24
    line_h = 30
    max_lines = (target.height - bar_h - 80) // line_h
    for line in lines[:max_lines]:
        draw.text((30, y), line, fill=INKY_PALETTE["BLACK"], font=body_font)
        y += line_h

    if footer:
        footer_font = _load_font(16)
        bbox = draw.textbbox((0, 0), footer, font=footer_font)
        fx = target.width - (bbox[2] - bbox[0]) - 20
        fy = target.height - 30
        draw.text((fx, fy), footer, fill=INKY_PALETTE["BLACK"], font=footer_font)

    return _to_jpeg(img)


def render_inbox_text(target: RenderTarget, sender: str, text: str, when: datetime) -> bytes:
    title = f"From: {sender or 'Anonymous'}"
    return render_title_body(
        target,
        title=title,
        body=text,
        accent="GREEN",
        footer=when.strftime("%a %d %b %H:%M"),
    )


def render_inbox_image(target: RenderTarget, image_bytes: bytes, sender: str | None) -> bytes:
    img = fit_image_to_target(image_bytes, target)

    if sender:
        draw = ImageDraw.Draw(img)
        footer_font = _load_font(16)
        label = f"From {sender}"
        bbox = draw.textbbox((0, 0), label, font=footer_font)
        pad = 6
        bx = target.width - (bbox[2] - bbox[0]) - pad * 2 - 12
        by = target.height - (bbox[3] - bbox[1]) - pad * 2 - 12
        draw.rectangle((bx, by, bx + (bbox[2] - bbox[0]) + pad * 2,
                        by + (bbox[3] - bbox[1]) + pad * 2),
                       fill=INKY_PALETTE["WHITE"], outline=INKY_PALETTE["BLACK"])
        draw.text((bx + pad, by + pad), label, fill=INKY_PALETTE["BLACK"], font=footer_font)

    return _to_jpeg(img)


def render_xkcd(target: RenderTarget, image_bytes: bytes, title: str, alt: str | None) -> bytes:
    img = Image.new("RGB", (target.width, target.height), INKY_PALETTE["WHITE"])
    draw = ImageDraw.Draw(img)

    title_h = 40
    title_font = _load_font(22, bold=True)
    draw.rectangle((0, 0, target.width, title_h), fill=INKY_PALETTE["BLACK"])
    draw.text((12, 8), f"XKCD - {title}", fill=INKY_PALETTE["WHITE"], font=title_font)

    comic = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    available_h = target.height - title_h - (40 if alt else 12)
    comic.thumbnail((target.width - 20, available_h), Image.LANCZOS)
    ox = (target.width - comic.width) // 2
    oy = title_h + 6
    img.paste(comic, (ox, oy))

    if alt:
        alt_font = _load_font(14)
        lines = _wrap(draw, alt, alt_font, target.width - 40)[:2]
        ay = target.height - len(lines) * 18 - 6
        for line in lines:
            draw.text((20, ay), line, fill=INKY_PALETTE["BLACK"], font=alt_font)
            ay += 18

    return _to_jpeg(img)


def render_weather(target: RenderTarget, current: dict, forecast: Iterable[dict]) -> bytes:
    img, draw = _new_canvas(target)

    bar_h = 64
    draw.rectangle((0, 0, target.width, bar_h), fill=INKY_PALETTE["BLUE"])
    title_font = _load_font(32, bold=True)
    draw.text((20, 14), f"Local Weather", fill=INKY_PALETTE["WHITE"], font=title_font)

    big_font = _load_font(96, bold=True)
    label_font = _load_font(20)
    cur_temp = f"{int(round(current.get('temperature', 0)))}\N{DEGREE SIGN}"
    draw.text((30, bar_h + 30), cur_temp, fill=INKY_PALETTE["RED"], font=big_font)
    cond = current.get("description", "")
    draw.text((30, bar_h + 140), cond, fill=INKY_PALETTE["BLACK"], font=label_font)
    extras = f"Wind {int(round(current.get('wind_speed', 0)))} km/h | Humidity {int(round(current.get('humidity', 0)))}%"
    draw.text((30, bar_h + 170), extras, fill=INKY_PALETTE["BLACK"], font=label_font)

    col_w = (target.width - 60) // 4
    col_x = 30
    col_y = target.height - 180
    day_font = _load_font(20, bold=True)
    temp_font = _load_font(28, bold=True)
    for i, day in enumerate(list(forecast)[:4]):
        x = col_x + i * col_w
        draw.rectangle((x, col_y, x + col_w - 12, col_y + 150), outline=INKY_PALETTE["BLACK"], width=2)
        draw.text((x + 10, col_y + 8), day.get("label", "")[:5], fill=INKY_PALETTE["BLUE"], font=day_font)
        hi = day.get("high")
        lo = day.get("low")
        draw.text((x + 10, col_y + 42),
                  f"{int(round(hi)) if hi is not None else '--'}\N{DEGREE SIGN}",
                  fill=INKY_PALETTE["RED"], font=temp_font)
        draw.text((x + 10, col_y + 86),
                  f"lo {int(round(lo)) if lo is not None else '--'}\N{DEGREE SIGN}",
                  fill=INKY_PALETTE["BLACK"], font=label_font)

    return _to_jpeg(img)


def render_bbc(target: RenderTarget, headlines: list[dict]) -> bytes:
    img, draw = _new_canvas(target)

    bar_h = 56
    draw.rectangle((0, 0, target.width, bar_h), fill=INKY_PALETTE["RED"])
    title_font = _load_font(28, bold=True)
    draw.text((20, 12), "BBC Headlines", fill=INKY_PALETTE["WHITE"], font=title_font)

    head_font = _load_font(22, bold=True)
    body_font = _load_font(16)
    y = bar_h + 16
    block_h = (target.height - bar_h - 32) // max(1, min(4, len(headlines)))
    for item in headlines[:4]:
        title = item.get("title", "")
        desc = item.get("description", "")
        title_lines = _wrap(draw, title, head_font, target.width - 40)[:2]
        for line in title_lines:
            draw.text((20, y), line, fill=INKY_PALETTE["BLACK"], font=head_font)
            y += 28
        desc_lines = _wrap(draw, desc, body_font, target.width - 40)[:2]
        for line in desc_lines:
            draw.text((20, y), line, fill=INKY_PALETTE["BLUE"], font=body_font)
            y += 20
        y += 8
        draw.line((20, y, target.width - 20, y), fill=INKY_PALETTE["BLACK"], width=1)
        y += 6
        if y >= bar_h + block_h * 4:
            break

    return _to_jpeg(img)
