"""Pillow-backed renderers that produce image payloads sized for an Inky Frame.

Frames receive server-dithered PNGs decoded by Pimoroni `pngdec` with frame-side
dithering disabled.
Fonts: we use the default Pillow truetype lookup; if the platform has
DejaVu (most Debian/Ubuntu containers do, including python:3.12-slim once we
install fonts-dejavu-core) we use that.
"""

from __future__ import annotations

import io
import math
import textwrap
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from collections.abc import Callable

import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .bitmap_font import draw_text, measure_text
from .inky_display import dither_image
from .link_preview import LinkPreview
from .reddit import REDDIT_ORANGE
from .url_clean import clean_url_for_qr

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
    has_sd_card: bool = False


def target_for(display_type: str, *, has_sd_card: bool = False) -> RenderTarget:
    w, h = DISPLAY_DIMENSIONS.get(display_type, (800, 480))
    return RenderTarget(w, h, has_sd_card=has_sd_card)


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


def _finalize_image(img: Image.Image, target: RenderTarget) -> bytes:
    """Apply final six-color Stucki dithering and encode as PNG."""
    buf = io.BytesIO()
    dither_image(img).save(buf, format="PNG", optimize=True)
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
    return _finalize_image(fit_image_to_target(image_bytes, target), target)


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

    return _finalize_image(img, target)


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

    return _finalize_image(img, target)


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

    return _finalize_image(img, target)


def _weather_theme(code: int) -> dict:
    gray = (130, 135, 145)
    if code in (0, 1):
        return {"accent": INKY_PALETTE["YELLOW"], "secondary": INKY_PALETTE["ORANGE"], "icon": "clear", "tint": (255, 248, 220)}
    if code == 2:
        return {"accent": INKY_PALETTE["YELLOW"], "secondary": INKY_PALETTE["BLUE"], "icon": "partly", "tint": (255, 250, 230)}
    if code == 3:
        return {"accent": gray, "secondary": INKY_PALETTE["BLUE"], "icon": "cloud", "tint": (235, 238, 242)}
    if code in (45, 48):
        return {"accent": gray, "secondary": INKY_PALETTE["BLACK"], "icon": "fog", "tint": (228, 230, 235)}
    if code in (71, 73, 75, 77):
        return {"accent": INKY_PALETTE["BLUE"], "secondary": INKY_PALETTE["WHITE"], "icon": "snow", "tint": (230, 240, 255)}
    if code in (95, 96, 99):
        return {"accent": INKY_PALETTE["ORANGE"], "secondary": INKY_PALETTE["RED"], "icon": "thunder", "tint": (245, 235, 230)}
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return {"accent": INKY_PALETTE["BLUE"], "secondary": INKY_PALETTE["GREEN"], "icon": "rain", "tint": (225, 238, 255)}
    return {"accent": INKY_PALETTE["BLUE"], "secondary": INKY_PALETTE["GREEN"], "icon": "rain", "tint": (225, 238, 255)}


def _draw_weather_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, icon: str, accent, secondary) -> None:
    s = size
    if icon == "clear":
        r = s // 5
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=accent)
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1 = cx + int(math.cos(rad) * r * 1.5)
            y1 = cy + int(math.sin(rad) * r * 1.5)
            x2 = cx + int(math.cos(rad) * r * 2.4)
            y2 = cy + int(math.sin(rad) * r * 2.4)
            draw.line((x1, y1, x2, y2), fill=accent, width=max(3, s // 28))
        return

    def _cloud(ox: int, oy: int, scale: float = 1.0) -> None:
        w = int(s * 0.55 * scale)
        h = int(s * 0.28 * scale)
        draw.ellipse((ox - w, oy, ox, oy + h), fill=secondary)
        draw.ellipse((ox - w // 2, oy - h, ox + w // 2, oy + h // 2), fill=secondary)
        draw.ellipse((ox, oy - h // 3, ox + w, oy + h), fill=secondary)

    if icon == "cloud":
        _cloud(cx, cy)
        return
    if icon == "partly":
        r = s // 6
        draw.ellipse((cx - s // 3 - r, cy - s // 5 - r, cx - s // 3 + r, cy - s // 5 + r), fill=accent)
        _cloud(cx + s // 10, cy + s // 12, 1.05)
        return
    if icon == "fog":
        for i, alpha in enumerate((0, 1, 2)):
            y = cy - s // 10 + i * (s // 7)
            draw.rounded_rectangle(
                (cx - s // 2, y, cx + s // 2, y + s // 10),
                radius=s // 20,
                fill=accent if i == 1 else secondary,
            )
        return
    if icon in {"rain", "snow", "thunder"}:
        _cloud(cx, cy - s // 10)
        base_y = cy + s // 5
        if icon == "rain":
            for dx in (-s // 5, 0, s // 5):
                draw.line((cx + dx, base_y, cx + dx - s // 18, base_y + s // 4), fill=accent, width=max(2, s // 32))
        elif icon == "snow":
            for dx in (-s // 5, 0, s // 5):
                draw.ellipse((cx + dx - 3, base_y, cx + dx + 3, base_y + 6), fill=accent)
        else:
            draw.polygon(
                [
                    (cx, base_y),
                    (cx + s // 10, base_y + s // 5),
                    (cx + 2, base_y + s // 5),
                    (cx + s // 12, base_y + s // 3),
                    (cx - s // 14, base_y + s // 6),
                    (cx + 2, base_y + s // 6),
                ],
                fill=accent,
            )


def _format_updated_at(iso_value: str | None, timezone: str | None) -> str | None:
    if not iso_value:
        return None
    try:
        from zoneinfo import ZoneInfo

        when = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        tz_name = timezone if timezone and timezone != "auto" else None
        if tz_name:
            tz = ZoneInfo(tz_name)
            if when.tzinfo is None:
                # Open-Meteo returns naive local times for the requested timezone.
                when = when.replace(tzinfo=tz)
            else:
                when = when.astimezone(tz)
        return when.strftime("%H:%M")
    except ValueError:
        if "T" in iso_value:
            return iso_value.split("T", 1)[1][:5]
        return None


def _graph_plot_box(x: int, y: int, width: int, height: int, *, precip: bool = False) -> tuple[int, int, int, int]:
    left = 44
    top = 22 if not precip else 22
    return x + left, y + top, width - 52, height - (30 if not precip else 30)


def _draw_now_marker(
    draw: ImageDraw.ImageDraw,
    plot_x: int,
    plot_y: int,
    plot_w: int,
    plot_h: int,
    n: int,
    now_index: int | None,
) -> None:
    if now_index is None or n < 2:
        return
    nx = plot_x + int(now_index * plot_w / max(1, n - 1))
    draw.line((nx, plot_y, nx, plot_y + plot_h), fill=(150, 155, 165), width=1)


def _series_values(points: Iterable[dict], key: str) -> list[float]:
    out: list[float] = []
    for point in points:
        val = point.get(key)
        if val is not None:
            out.append(float(val))
    return out


def _draw_series_graph(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    height: int,
    values: list[float],
    *,
    color,
    fill: tuple[int, int, int] | None = None,
    y_min: float | None = None,
    y_max: float | None = None,
    label: str,
    value_fmt: Callable[[float], str],
    now_index: int | None = None,
) -> None:
    if not values:
        return
    plot_x, plot_y, plot_w, plot_h = _graph_plot_box(x, y, width, height)
    lo = y_min if y_min is not None else min(values)
    hi = y_max if y_max is not None else max(values)
    if hi == lo:
        hi += 1
        lo -= 1
    draw.rectangle((x, y, x + width, y + height), outline=INKY_PALETTE["BLACK"], width=1)
    label_font = _load_font(14, bold=True)
    draw.text((x + 8, y + 4), label, fill=INKY_PALETTE["BLACK"], font=label_font)
    draw.text((x + 4, plot_y), value_fmt(hi), fill=INKY_PALETTE["BLACK"], font=_load_font(12))
    draw.text((x + 4, plot_y + plot_h - 14), value_fmt(lo), fill=INKY_PALETTE["BLACK"], font=_load_font(12))

    coords: list[tuple[int, int]] = []
    n = len(values)
    for i, val in enumerate(values):
        px = plot_x + int(i * plot_w / max(1, n - 1))
        norm = (val - lo) / (hi - lo)
        py = plot_y + plot_h - int(norm * plot_h)
        coords.append((px, py))

    if fill and len(coords) >= 2:
        area = coords + [(coords[-1][0], plot_y + plot_h), (coords[0][0], plot_y + plot_h)]
        draw.polygon(area, fill=fill)

    if len(coords) >= 2:
        draw.line(coords, fill=color, width=3)
    elif coords:
        draw.ellipse((coords[0][0] - 4, coords[0][1] - 4, coords[0][0] + 4, coords[0][1] + 4), fill=color)
    _draw_now_marker(draw, plot_x, plot_y, plot_w, plot_h, n, now_index)


def _draw_precip_graph(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    height: int,
    values: list[float],
    *,
    color,
    now_index: int | None = None,
) -> None:
    if not values:
        return
    plot_x, plot_y, plot_w, plot_h = _graph_plot_box(x, y, width, height, precip=True)
    draw.rectangle((x, y, x + width, y + height), outline=INKY_PALETTE["BLACK"], width=1)
    label_font = _load_font(14, bold=True)
    draw.text((x + 8, y + 4), "Rain %", fill=INKY_PALETTE["BLACK"], font=label_font)
    n = len(values)
    bar_w = max(2, plot_w // max(1, n) - 2)
    for i, val in enumerate(values):
        bx = plot_x + int(i * plot_w / max(1, n - 1)) - bar_w // 2
        bh = int((max(0.0, min(100.0, val)) / 100.0) * plot_h)
        by = plot_y + plot_h - bh
        draw.rectangle((bx, by, bx + bar_w, plot_y + plot_h), fill=color)
    _draw_now_marker(draw, plot_x, plot_y, plot_w, plot_h, n, now_index)


def _moon_phase_angle(illumination: float | None, waxing: bool) -> float:
    """Phase angle on the sphere (radians): 0 = new, π = full."""
    frac = max(0.0, min(1.0, (illumination if illumination is not None else 50.0) / 100.0))
    if frac >= 0.999:
        return math.pi
    if frac <= 0.001:
        return 0.0
    phase = math.acos(1.0 - 2.0 * frac)
    return phase if waxing else (2.0 * math.pi - phase)


def _render_moon_phase_image(size: int, illumination: float | None, *, waxing: bool = True) -> Image.Image:
    """Spherical terminator with 2° soft edge (celestialprogramming.com/moonPhaseRender)."""
    diameter = max(32, size * 2)
    r = diameter / 2.0
    dark = (48, 52, 68)
    light = INKY_PALETTE["YELLOW"]
    moon = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    pixels = moon.load()
    phase = _moon_phase_angle(illumination, waxing)
    cos_p = math.cos(phase)
    sin_p = math.sin(phase)
    grad = math.radians(2.0)

    for py in range(diameter):
        for px in range(diameter):
            nx = (px - r + 0.5) / r
            ny = (py - r + 0.5) / r
            if nx * nx + ny * ny > 1.0:
                continue
            nz = math.sqrt(1.0 - nx * nx - ny * ny)
            if waxing:
                metric = cos_p * nx - sin_p * nz
            else:
                metric = -cos_p * nx + sin_p * nz
            if metric >= grad:
                t = 1.0
            elif metric <= -grad:
                t = 0.0
            else:
                t = 0.5 + metric / (2.0 * grad)
            shade = tuple(int(dark[i] + t * (light[i] - dark[i])) for i in range(3))
            pixels[px, py] = shade + (255,)

    if diameter != size:
        moon = moon.resize((size, size), Image.LANCZOS)
    return moon


def _paste_moon_phase(
    img: Image.Image,
    cx: int,
    cy: int,
    size: int,
    illumination: float | None,
    *,
    waxing: bool = True,
) -> None:
    moon = _render_moon_phase_image(size, illumination, waxing=waxing)
    ox = cx - moon.width // 2
    oy = cy - moon.height // 2
    img.paste(moon, (ox, oy), moon)


def render_weather(target: RenderTarget, payload: dict) -> bytes:
    current = payload.get("current", {})
    hourly = payload.get("hourly", [])
    code = int(current.get("code", 0))
    theme = _weather_theme(code)
    accent = theme["accent"]
    secondary = theme["secondary"]
    tint = theme["tint"]

    img = Image.new("RGB", (target.width, target.height), tint)
    draw = ImageDraw.Draw(img)

    scale = target.height / 480
    margin = int(16 * scale)
    footer_h = int(56 * scale)
    hero_h = int(target.height * 0.34)
    graph_gap = int(6 * scale)
    graph_rows = 2
    graph_cols = 2
    graph_h = (target.height - hero_h - footer_h - graph_gap * (graph_rows + 1)) // graph_rows
    graph_w = (target.width - margin * (graph_cols + 1)) // graph_cols

    draw.rectangle((0, 0, target.width, int(10 * scale)), fill=accent)
    icon_size = int(min(hero_h * 0.7, target.width * 0.22))
    icon_cx = margin + icon_size // 2
    icon_cy = hero_h // 2 + int(8 * scale)
    _draw_weather_icon(draw, icon_cx, icon_cy, icon_size, theme["icon"], accent, secondary)

    temp_font = _load_font(int(72 * scale), bold=True)
    cond_font = _load_font(int(22 * scale))
    meta_font = _load_font(int(16 * scale))
    unit_sym = "\N{DEGREE SIGN}F" if payload.get("units") == "fahrenheit" else "\N{DEGREE SIGN}C"
    temp_text = f"{int(round(current.get('temperature', 0)))}{unit_sym}"
    tx = icon_cx + icon_size // 2 + margin
    ty = int(hero_h * 0.22)
    draw.text((tx, ty), temp_text, fill=INKY_PALETTE["BLACK"], font=temp_font)
    draw.text((tx, ty + int(78 * scale)), current.get("description", ""), fill=secondary, font=cond_font)
    draw.text(
        (tx, ty + int(110 * scale)),
        f"Humidity {int(round(current.get('humidity', 0)))}%",
        fill=INKY_PALETTE["BLACK"],
        font=meta_font,
    )

    moon = payload.get("moon") or {}
    moon_size = int(min(hero_h * 0.5, 80 * scale))
    moon_cx = target.width - margin - moon_size // 2
    moon_cy = ty + moon_size // 2
    if moon:
        _paste_moon_phase(
            img,
            moon_cx,
            moon_cy,
            moon_size,
            moon.get("illumination"),
            waxing=moon.get("waxing", True),
        )

    graph_y = hero_h + graph_gap
    now_index = payload.get("current_hour_index")
    temps = _series_values(hourly, "temperature")
    precips = _series_values(hourly, "precip_prob")
    winds = _series_values(hourly, "wind_speed")
    uv_values = _series_values(hourly, "uv_index")
    wind_unit = payload.get("wind_unit", "km/h")
    temp_fmt = lambda v: f"{int(round(v))}{unit_sym[-1:]}"

    graphs = [
        (temps, {"color": accent, "fill": tint, "label": "Temp", "value_fmt": temp_fmt, "kind": "line"}),
        (precips, {"color": secondary, "label": "Rain %", "kind": "precip"}),
        (winds, {"color": accent, "label": f"Wind ({wind_unit})", "value_fmt": lambda v: str(int(round(v))), "kind": "line"}),
        (uv_values, {"color": accent, "fill": tint, "label": "UV index", "value_fmt": lambda v: f"{v:.0f}", "kind": "line", "y_min": 0, "y_max": 12}),
    ]
    for idx, (values, opts) in enumerate(graphs):
        row, col = divmod(idx, graph_cols)
        gx = margin + col * (graph_w + margin)
        gy = graph_y + row * (graph_h + graph_gap)
        if opts["kind"] == "precip":
            _draw_precip_graph(draw, gx, gy, graph_w, graph_h, values, color=opts["color"], now_index=now_index)
        else:
            _draw_series_graph(
                draw, gx, gy, graph_w, graph_h, values,
                color=opts["color"],
                fill=opts.get("fill"),
                y_min=opts.get("y_min"),
                y_max=opts.get("y_max"),
                label=opts["label"],
                value_fmt=opts["value_fmt"],
                now_index=now_index,
            )

    footer_y = target.height - footer_h
    draw.rectangle((0, footer_y, target.width, target.height), fill=INKY_PALETTE["WHITE"])
    draw.line((margin, footer_y, target.width - margin, footer_y), fill=accent, width=2)
    footer_font = _load_font(int(18 * scale), bold=True)
    detail_font = _load_font(int(16 * scale))
    wind_now = int(round(current.get("wind_speed", 0)))
    sunrise = payload.get("sunrise") or "--:--"
    sunset = payload.get("sunset") or "--:--"
    cols = [
        ("Sunrise", sunrise),
        ("Sunset", sunset),
        ("Wind now", f"{wind_now} {wind_unit}"),
    ]
    col_w = (target.width - margin * 2) // len(cols)
    for i, (label, value) in enumerate(cols):
        cx = margin + i * col_w
        draw.text((cx, footer_y + int(10 * scale)), label, fill=secondary, font=detail_font)
        draw.text((cx, footer_y + int(32 * scale)), value, fill=INKY_PALETTE["BLACK"], font=footer_font)

    updated = _format_updated_at(payload.get("updated_at"), payload.get("timezone"))
    if updated:
        label_font = _load_font(max(12, int(13 * scale)))
        stamp_font = _load_font(max(16, int(16 * scale)), bold=True)
        label = "Last Updated:"
        label_bbox = draw.textbbox((0, 0), label, font=label_font)
        time_bbox = draw.textbbox((0, 0), updated, font=stamp_font)
        label_w = label_bbox[2] - label_bbox[0]
        label_h = label_bbox[3] - label_bbox[1]
        time_w = time_bbox[2] - time_bbox[0]
        time_h = time_bbox[3] - time_bbox[1]
        line_gap = max(2, int(3 * scale))
        block_h = label_h + line_gap + time_h
        stamp_y = target.height - margin - block_h
        draw.text(
            (target.width - margin - label_w, stamp_y),
            label,
            fill=accent,
            font=label_font,
        )
        draw.text(
            (target.width - margin - time_w, stamp_y + label_h + line_gap),
            updated,
            fill=INKY_PALETTE["BLACK"],
            font=stamp_font,
        )

    return _finalize_image(img, target)


def _draw_qr_code(img: Image.Image, ox: int, oy: int, size: int, payload: str) -> None:
    payload = clean_url_for_qr(payload)
    if not payload:
        return
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=0,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    modules = len(matrix)
    if modules == 0:
        return

    tile = Image.new("1", (modules, modules), 1)
    px_map = tile.load()
    for row, line in enumerate(matrix):
        for col, on in enumerate(line):
            if on:
                px_map[col, row] = 0

    scaled = tile.resize((size, size), Image.NEAREST)
    qr_rgb = Image.new("RGB", (size, size), INKY_PALETTE["WHITE"])
    src = scaled.load()
    dst = qr_rgb.load()
    black = INKY_PALETTE["BLACK"]
    white = INKY_PALETTE["WHITE"]
    for y in range(size):
        for x in range(size):
            dst[x, y] = black if src[x, y] == 0 else white
    img.paste(qr_rgb, (ox, oy))


def _draw_qr_badge(img: Image.Image, x: int, y: int, size: int, payload: str) -> None:
    draw = ImageDraw.Draw(img)
    pad = max(6, size // 14)
    draw.rectangle(
        (x - pad, y - pad, x + size + pad, y + size + pad),
        fill=INKY_PALETTE["WHITE"],
        outline=INKY_PALETTE["BLACK"],
        width=2,
    )
    _draw_qr_code(img, x, y, size, payload)


def render_fullscreen_qr(target: RenderTarget, url: str, title: str = "Open link") -> bytes:
    img, draw = _new_canvas(target)
    clean = clean_url_for_qr(url)
    margin = max(18, target.width // 40)
    title_font = _load_font(max(26, target.height // 16), bold=True)
    small_font = _load_font(max(14, target.height // 32))
    draw.rectangle((0, 0, target.width, max(56, target.height // 8)), fill=INKY_PALETTE["BLACK"])
    draw.text((margin, margin), title, fill=INKY_PALETTE["WHITE"], font=title_font)

    qr_size = min(target.width - margin * 2, target.height - max(110, target.height // 4))
    qr_size = max(120, qr_size)
    qr_x = (target.width - qr_size) // 2
    qr_y = max(70, (target.height - qr_size) // 2)
    _draw_qr_code(img, qr_x, qr_y, qr_size, clean)

    lines = _wrap(draw, clean, small_font, target.width - margin * 2)[:2]
    y = min(target.height - margin - len(lines) * 20, qr_y + qr_size + margin)
    for line in lines:
        draw.text((margin, y), line, fill=INKY_PALETTE["BLACK"], font=small_font)
        y += 20
    return _finalize_image(img, target)


def render_link_preview(target: RenderTarget, preview: LinkPreview) -> bytes:
    if preview.is_direct_image and preview.image_bytes:
        img = fit_image_to_target(preview.image_bytes, target)
        qr_size = max(84, min(target.width, target.height) // 5)
        _draw_qr_badge(img, target.width - qr_size - 20, target.height - qr_size - 20, qr_size, preview.final_url)
        return _finalize_image(img, target)

    if not preview.title and not preview.description and not preview.image_bytes:
        return render_fullscreen_qr(target, preview.final_url)

    img, draw = _new_canvas(target)
    margin = max(20, target.width // 36)
    header_h = max(54, target.height // 9)
    draw.rectangle((0, 0, target.width, header_h), fill=INKY_PALETTE["BLUE"])

    domain_font = _load_font(max(20, target.height // 22), bold=True)
    title_font = _load_font(max(30, target.height // 14), bold=True)
    body_font = _load_font(max(18, target.height // 25))
    small_font = _load_font(max(14, target.height // 34))

    draw.text((margin, (header_h - domain_font.size) // 2), preview.domain, fill=INKY_PALETTE["WHITE"], font=domain_font)

    qr_size = max(84, min(target.width, target.height) // 5)
    qr_x = target.width - qr_size - margin
    qr_y = target.height - qr_size - margin

    has_image = bool(preview.image_bytes)
    image_col_x = int(target.width * 2 / 3)
    image_col_w = target.width - image_col_x - margin
    content_x = margin
    content_w = (image_col_x - margin * 2) if has_image else (target.width - margin * 2)
    y = header_h + margin

    if has_image:
        try:
            thumb = Image.open(io.BytesIO(preview.image_bytes))
            thumb = ImageOps.exif_transpose(thumb).convert("RGB")
            thumb_w = max(80, image_col_w - margin // 2)
            thumb_h = max(80, qr_y - header_h - margin * 3)
            thumb.thumbnail((thumb_w, thumb_h), Image.LANCZOS)
            tx = image_col_x + (image_col_w - thumb.width) // 2
            ty = header_h + (qr_y - header_h - thumb.height) // 2
            draw.rectangle((tx - 4, ty - 4, tx + thumb.width + 4, ty + thumb.height + 4), outline=INKY_PALETTE["BLACK"], width=2)
            img.paste(thumb, (tx, ty))
        except Exception:
            content_w = target.width - margin * 2
            pass

    title = preview.title or "Open link"
    max_title_lines = 3
    min_title_size = max(22, target.height // 22)
    while title_font.size > min_title_size and len(_wrap(draw, title, title_font, content_w)) > max_title_lines:
        title_font = _load_font(title_font.size - 2, bold=True)
    title_lines = _wrap(draw, title, title_font, content_w)[:max_title_lines]
    for line in title_lines:
        draw.text((content_x, y), line, fill=INKY_PALETTE["BLACK"], font=title_font)
        y += title_font.size + 6

    if preview.description:
        y += 8
        available_h = max(70, qr_y - y - margin)
        max_lines = max(2, available_h // (body_font.size + 7))
        body_lines = _wrap(draw, preview.description, body_font, content_w)
        min_body_size = max(14, target.height // 34)
        while body_font.size > min_body_size and len(body_lines) > max_lines:
            body_font = _load_font(body_font.size - 1)
            max_lines = max(2, available_h // (body_font.size + 6))
            body_lines = _wrap(draw, preview.description, body_font, content_w)
        for line in body_lines[:max_lines]:
            draw.text((margin, y), line, fill=INKY_PALETTE["BLUE"], font=body_font)
            y += body_font.size + 6

    draw.line((margin, qr_y - 14, target.width - margin, qr_y - 14), fill=INKY_PALETTE["BLACK"], width=1)
    _draw_qr_badge(img, qr_x, qr_y, qr_size, preview.final_url)
    url_lines = _wrap(draw, preview.final_url, small_font, max(120, qr_x - margin * 2))[:3]
    uy = qr_y + 6
    for line in url_lines:
        draw.text((margin, uy), line, fill=INKY_PALETTE["BLACK"], font=small_font)
        uy += small_font.size + 4

    return _finalize_image(img, target)


def _magazine_layout_scale(target: RenderTarget) -> tuple[float, float]:
    base_w, base_h = 800, 480
    return target.width / base_w, target.height / base_h


def _draw_reddit_icon(draw: ImageDraw.ImageDraw, x: int, y: int, size: int) -> None:
    """Simplified Reddit Snoo mark for the header."""
    orange = REDDIT_ORANGE
    white = INKY_PALETTE["WHITE"]
    black = INKY_PALETTE["BLACK"]

    draw.ellipse((x, y, x + size, y + size), fill=orange, outline=black, width=max(1, size // 16))

    pad = max(2, size // 6)
    face = (x + pad, y + pad + size // 10, x + size - pad, y + size - pad)
    draw.ellipse(face, fill=white, outline=black, width=max(1, size // 18))

    cx = x + size // 2
    antenna_h = max(3, size // 5)
    stem_top = y + pad // 2
    draw.line((cx, face[1], cx, stem_top + antenna_h), fill=orange, width=max(2, size // 10))
    dot_r = max(2, size // 10)
    draw.ellipse((cx - dot_r, stem_top, cx + dot_r, stem_top + dot_r * 2), fill=orange, outline=black)

    eye_r = max(2, size // 14)
    eye_y = y + size // 2 - size // 14
    draw.ellipse((cx - size // 5 - eye_r, eye_y - eye_r, cx - size // 5 + eye_r, eye_y + eye_r), fill=orange)
    draw.ellipse((cx + size // 5 - eye_r, eye_y - eye_r, cx + size // 5 + eye_r, eye_y + eye_r), fill=orange)

    smile_y = y + size // 2 + size // 8
    draw.arc(
        (cx - size // 4, smile_y - size // 10, cx + size // 4, smile_y + size // 5),
        start=200,
        end=340,
        fill=orange,
        width=max(2, size // 12),
    )


def _render_magazine_layout(
    target: RenderTarget,
    *,
    items: list[dict],
    header_text: str,
    header_color: tuple[int, int, int],
    title_color: tuple[int, int, int],
    body_color: tuple[int, int, int],
    header_icon: Callable[[ImageDraw.ImageDraw, int, int, int], None] | None = None,
    empty_title: str = "Unable to display feed!",
    empty_hint: str = "Check your settings in the portal.",
) -> bytes:
    """Two-story magazine layout with QR codes (Pimoroni news_headlines style)."""
    img, draw = _new_canvas(target)
    sx, sy = _magazine_layout_scale(target)

    def px(x: float) -> int:
        return int(x * sx)

    def py(y: float) -> int:
        return int(y * sy)

    def psize(s: float) -> int:
        return max(1, int(s * min(sx, sy)))

    black = INKY_PALETTE["BLACK"]
    header_h = py(40)
    footer_h = py(20)
    qr_size = psize(100)
    icon_size = psize(34) if header_icon else 0
    header_text_x = px(10) + icon_size + (px(8) if icon_size else 0)

    if not items:
        mid = target.height // 2
        draw.rectangle((0, mid - py(20), target.width, mid + py(20)), fill=header_color)
        draw_text(draw, px(5), mid - py(15), empty_title, black, max_width=target.width - px(10), scale=psize(2))
        draw_text(draw, px(5), mid + py(2), empty_hint, black, max_width=target.width - px(10), scale=psize(2))
        return _finalize_image(img, target)

    draw.rectangle((0, 0, target.width, header_h), fill=header_color)
    if header_icon:
        header_icon(draw, px(6), py(4), icon_size)
    draw_text(
        draw,
        header_text_x,
        py(10),
        header_text,
        black,
        max_width=target.width - header_text_x - px(10),
        scale=psize(3),
    )

    first = items[0]
    second = items[1] if len(items) > 1 else None

    title0 = first.get("title", "") or "Untitled"
    desc0 = first.get("description", "") or ""
    title_scale0 = psize(3) if measure_text(title0) < target.width else psize(2)
    desc_y0 = py(155) if measure_text(title0) < px(650) else py(130)
    draw_text(draw, px(10), py(70), title0, title_color, max_width=target.width - px(150), scale=title_scale0)
    draw_text(draw, px(10), desc_y0, desc0, body_color, max_width=target.width - px(150), scale=psize(2))
    _draw_qr_code(img, target.width - px(110), py(65), qr_size, first.get("guid") or first.get("link") or "")

    draw.line((px(10), py(215), target.width - px(10), py(215)), fill=black, width=max(1, psize(1)))

    if second:
        title1 = second.get("title", "") or "Untitled"
        desc1 = second.get("description", "") or ""
        title_scale1 = psize(3) if measure_text(title1) < target.width else psize(2)
        desc_y1 = py(320) if measure_text(title1) < px(650) else py(340)
        draw_text(draw, px(130), py(260), title1, title_color, max_width=target.width - px(140), scale=title_scale1)
        draw_text(draw, px(130), desc_y1, desc1, body_color, max_width=target.width - px(145), scale=psize(2))
        _draw_qr_code(img, px(10), py(265), qr_size, second.get("guid") or second.get("link") or "")

    draw.rectangle((0, target.height - footer_h, target.width, target.height), fill=header_color)
    return _finalize_image(img, target)


def render_rss_magazine(target: RenderTarget, feed_title: str, items: list[dict]) -> bytes:
    return _render_magazine_layout(
        target,
        items=items,
        header_text=f"Headlines from {feed_title}:",
        header_color=INKY_PALETTE["RED"],
        title_color=INKY_PALETTE["RED"],
        body_color=INKY_PALETTE["BLUE"],
        empty_hint="Check the feed URL in the portal.",
    )


def render_reddit_magazine(target: RenderTarget, label: str, items: list[dict]) -> bytes:
    """Three-up Reddit layout: titles and QR codes only (no RSS blurbs)."""
    posts = items[:3]
    img, draw = _new_canvas(target)
    sx, sy = _magazine_layout_scale(target)

    def px(x: float) -> int:
        return int(x * sx)

    def py(y: float) -> int:
        return int(y * sy)

    def psize(s: float) -> int:
        return max(1, int(s * min(sx, sy)))

    black = INKY_PALETTE["BLACK"]
    header_h = py(40)
    footer_h = py(20)
    margin = px(10)
    icon_size = psize(34)
    header_text_x = px(10) + icon_size + px(8)

    if not posts:
        mid = target.height // 2
        draw.rectangle((0, mid - py(20), target.width, mid + py(20)), fill=REDDIT_ORANGE)
        draw_text(draw, px(5), mid - py(15), "Unable to load subreddit!", black, max_width=target.width - px(10), scale=psize(2))
        draw_text(draw, px(5), mid + py(2), "Check the subreddit name in the portal.", black, max_width=target.width - px(10), scale=psize(2))
        return _finalize_image(img, target)

    draw.rectangle((0, 0, target.width, header_h), fill=REDDIT_ORANGE)
    _draw_reddit_icon(draw, px(6), py(4), icon_size)
    draw_text(
        draw,
        header_text_x,
        py(10),
        f"{label}:",
        black,
        max_width=target.width - header_text_x - px(10),
        scale=psize(3),
    )

    content_top = header_h + py(8)
    content_bottom = target.height - footer_h - py(8)
    block_h = max(1, (content_bottom - content_top) // len(posts))
    qr_size = max(psize(56), min(psize(80), block_h - py(16)))

    for index, item in enumerate(posts):
        y0 = content_top + index * block_h
        qr_x = target.width - qr_size - margin
        qr_y = y0 + (block_h - qr_size) // 2
        title = item.get("title", "") or "Untitled"
        title_max_w = qr_x - margin * 2
        title_scale = psize(3) if measure_text(title) < title_max_w else psize(2)
        draw_text(
            draw,
            margin,
            y0 + py(6),
            title,
            REDDIT_ORANGE,
            max_width=title_max_w,
            scale=title_scale,
        )
        _draw_qr_code(img, qr_x, qr_y, qr_size, item.get("guid") or item.get("link") or "")

        if index < len(posts) - 1:
            draw.line((margin, y0 + block_h - 1, target.width - margin, y0 + block_h - 1), fill=black, width=1)

    draw.rectangle((0, target.height - footer_h, target.width, target.height), fill=REDDIT_ORANGE)
    return _finalize_image(img, target)
