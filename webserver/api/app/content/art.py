"""Procedural art renderers for schedule items."""

from __future__ import annotations

import io
import math
import random
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .inky_display import dither_image
from .renderer import INKY_PALETTE, RenderTarget


ART_VARIANTS = {"night_sky", "mandelbrot", "location_rings", "wind_field"}


def _encode_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", compress_level=6)
    return buf.getvalue()


def _finalize(img: Image.Image) -> bytes:
    return _encode_png(dither_image(img))


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_to_target(image: Image.Image, target: RenderTarget) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        bg = Image.new("RGBA", image.size, INKY_PALETTE["WHITE"] + (255,))
        bg.alpha_composite(image.convert("RGBA"))
        image = bg.convert("RGB")
    else:
        image = image.convert("RGB")
    image.thumbnail((target.width, target.height), Image.LANCZOS)
    canvas = Image.new("RGB", (target.width, target.height), INKY_PALETTE["WHITE"])
    canvas.paste(image, ((target.width - image.width) // 2, (target.height - image.height) // 2))
    return canvas


def _label(draw: ImageDraw.ImageDraw, target: RenderTarget, title: str, subtitle: str) -> None:
    pad = 16
    title_font = _font(24, bold=True)
    sub_font = _font(15)
    title_box = draw.textbbox((0, 0), title, font=title_font)
    sub_box = draw.textbbox((0, 0), subtitle, font=sub_font)
    box_w = max(title_box[2] - title_box[0], sub_box[2] - sub_box[0]) + pad * 2
    box_h = 58
    x0 = target.width - box_w - 14
    y0 = target.height - box_h - 12
    draw.rectangle((x0, y0, target.width - 12, target.height - 10), fill=INKY_PALETTE["WHITE"])
    draw.line((x0, y0, target.width - 12, y0), fill=INKY_PALETTE["BLUE"], width=3)
    draw.text((x0 + pad, y0 + 7), title, fill=INKY_PALETTE["BLACK"], font=title_font)
    draw.text((x0 + pad, y0 + 34), subtitle, fill=INKY_PALETTE["BLUE"], font=sub_font)


def render_night_sky(
    target: RenderTarget,
    *,
    latitude: float,
    longitude: float,
    observed_at: datetime,
    show_labels: bool = True,
    magnitude: float = 4.8,
) -> bytes:
    try:
        from starplot import Observer, ZenithPlot, _
        from starplot.styles import PlotStyle, extensions
    except Exception as exc:
        raise RuntimeError("Starplot is not installed in the API container.") from exc

    observer = Observer(dt=observed_at, lat=latitude, lon=longitude)
    style = PlotStyle().extend(extensions.BLUE_MEDIUM)
    resolution = max(1400, min(2600, max(target.width, target.height) * 4))
    plot = ZenithPlot(observer=observer, style=style, resolution=resolution, autoscale=True)
    plot.horizon()
    plot.constellations()
    plot.stars(
        where=[_.magnitude < max(3.5, min(6.2, magnitude))],
        where_labels=[_.magnitude < 2.5] if show_labels else [False],
    )
    plot.milky_way()
    if show_labels:
        plot.constellation_labels()

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "night-sky.png"
        plot.export(str(out), transparent=True, padding=0.1)
        with Image.open(out) as exported:
            img = exported.copy()

    fitted = _fit_to_target(img, target)
    draw = ImageDraw.Draw(fitted)
    _label(draw, target, "Night sky", observed_at.strftime("%b %-d, %-I:%M %p"))
    return _finalize(fitted)


def render_mandelbrot(target: RenderTarget, *, seed: str, palette: str = "midnight") -> bytes:
    rng = random.Random(seed)
    cx = -0.745 + rng.uniform(-0.035, 0.035)
    cy = 0.115 + rng.uniform(-0.035, 0.035)
    zoom = rng.uniform(0.9, 1.8)
    span_x = 3.0 / zoom
    span_y = span_x * target.height / target.width
    max_iter = 72
    img = Image.new("RGB", (target.width, target.height), INKY_PALETTE["WHITE"])
    pix = img.load()
    colors = (
        [INKY_PALETTE[c] for c in ("WHITE", "YELLOW", "ORANGE", "RED", "BLUE", "BLACK")]
        if palette == "ember"
        else [INKY_PALETTE[c] for c in ("WHITE", "GREEN", "BLUE", "BLACK", "RED", "YELLOW")]
    )

    for y in range(target.height):
        im = cy - span_y / 2 + (y / max(1, target.height - 1)) * span_y
        for x in range(target.width):
            re = cx - span_x / 2 + (x / max(1, target.width - 1)) * span_x
            zr = zi = 0.0
            n = 0
            while zr * zr + zi * zi <= 4.0 and n < max_iter:
                zr, zi = zr * zr - zi * zi + re, 2 * zr * zi + im
                n += 1
            pix[x, y] = INKY_PALETTE["BLACK"] if n == max_iter else colors[(n // 5) % len(colors)]

    draw = ImageDraw.Draw(img)
    _label(draw, target, "Mandelbrot", "Daily viewport")
    return _finalize(img)


def render_location_rings(
    target: RenderTarget,
    *,
    latitude: float,
    longitude: float,
    observed_at: datetime,
) -> bytes:
    img = Image.new("RGB", (target.width, target.height), INKY_PALETTE["WHITE"])
    draw = ImageDraw.Draw(img)
    seed = f"{latitude:.4f}:{longitude:.4f}:{observed_at:%Y-%m-%d}"
    rng = random.Random(seed)
    cx = int(target.width * (0.5 + math.sin(math.radians(longitude)) * 0.16))
    cy = int(target.height * (0.5 - math.sin(math.radians(latitude)) * 0.16))
    colors = [INKY_PALETTE[c] for c in ("BLUE", "GREEN", "YELLOW", "RED", "BLACK")]
    max_r = int(math.hypot(target.width, target.height))

    for i, radius in enumerate(range(18, max_r, 17)):
        wobble = rng.randint(-5, 5)
        color = colors[i % len(colors)]
        width = 2 + (i % 3 == 0)
        box = (cx - radius + wobble, cy - radius - wobble, cx + radius + wobble, cy + radius - wobble)
        draw.ellipse(box, outline=color, width=width)

    for _ in range(42):
        x = rng.randrange(target.width)
        y = rng.randrange(target.height)
        r = rng.randrange(2, 7)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=colors[rng.randrange(len(colors))])

    _label(draw, target, "Location rings", f"{latitude:.2f}, {longitude:.2f}")
    return _finalize(img)


def render_wind_field(
    target: RenderTarget,
    *,
    latitude: float | None,
    longitude: float | None,
    observed_at: datetime,
) -> bytes:
    img = Image.new("RGB", (target.width, target.height), INKY_PALETTE["WHITE"])
    draw = ImageDraw.Draw(img)
    lat = latitude or 0.0
    lon = longitude or 0.0
    phase = observed_at.timetuple().tm_yday / 365 * math.tau
    colors = [INKY_PALETTE[c] for c in ("BLUE", "GREEN", "BLACK", "RED")]
    step = max(24, min(target.width, target.height) // 10)

    for y in range(step // 2, target.height, step):
        for x in range(step // 2, target.width, step):
            angle = (
                math.sin(x * 0.018 + phase + lon * 0.03)
                + math.cos(y * 0.021 - phase + lat * 0.03)
            ) * math.pi
            length = step * (0.45 + 0.25 * math.sin(angle + phase))
            x2 = x + math.cos(angle) * length
            y2 = y + math.sin(angle) * length
            color = colors[(x // step + y // step) % len(colors)]
            draw.line((x, y, x2, y2), fill=color, width=3)
            ah = 5
            draw.line((x2, y2, x2 - math.cos(angle - 0.6) * ah, y2 - math.sin(angle - 0.6) * ah), fill=color, width=2)
            draw.line((x2, y2, x2 - math.cos(angle + 0.6) * ah, y2 - math.sin(angle + 0.6) * ah), fill=color, width=2)

    _label(draw, target, "Vector field", observed_at.strftime("%Y day %j"))
    return _finalize(img)


def art_seed(config: dict[str, Any], observed_at: datetime, latitude: float | None, longitude: float | None) -> str:
    mode = str(config.get("seed_mode") or "daily")
    if mode == "fixed":
        return str(config.get("seed") or "inky-easel")
    if mode == "poll":
        return f"{observed_at.isoformat()}:{latitude}:{longitude}"
    return f"{observed_at:%Y-%m-%d}:{latitude}:{longitude}"
