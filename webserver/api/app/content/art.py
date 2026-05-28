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


def _cover_target(image: Image.Image, target: RenderTarget, zoom: float = 1.0) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGBA")
    fitted = ImageOps.fit(image, (target.width, target.height), method=Image.LANCZOS, centering=(0.5, 0.5))
    if zoom <= 1:
        return fitted
    scaled_size = (math.ceil(target.width * zoom), math.ceil(target.height * zoom))
    fitted = fitted.resize(scaled_size, Image.LANCZOS)
    left = (fitted.width - target.width) // 2
    top = (fitted.height - target.height) // 2
    return fitted.crop((left, top, left + target.width, top + target.height))


def _black_yellow_white_chart(image: Image.Image, target: RenderTarget) -> Image.Image:
    rgba = _cover_target(image, target, zoom=1.18)
    alpha = rgba.getchannel("A")
    mask = alpha.load()
    width, height = rgba.size
    visited = bytearray(width * height)
    out = Image.new("RGB", (width, height), INKY_PALETTE["BLACK"])
    pix = out.load()
    white = INKY_PALETTE["WHITE"]
    yellow = INKY_PALETTE["YELLOW"]

    for y in range(height):
        for x in range(width):
            idx = y * width + x
            if visited[idx] or mask[x, y] < 32:
                continue

            stack = [(x, y)]
            visited[idx] = 1
            points: list[tuple[int, int, int]] = []
            min_x = max_x = x
            min_y = max_y = y
            while stack:
                px, py = stack.pop()
                a = mask[px, py]
                points.append((px, py, a))
                min_x = min(min_x, px)
                max_x = max(max_x, px)
                min_y = min(min_y, py)
                max_y = max(max_y, py)
                for nx, ny in ((px - 1, py), (px + 1, py), (px, py - 1), (px, py + 1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        nidx = ny * width + nx
                        if not visited[nidx] and mask[nx, ny] >= 32:
                            visited[nidx] = 1
                            stack.append((nx, ny))

            comp_w = max_x - min_x + 1
            comp_h = max_y - min_y + 1
            is_star = len(points) <= 180 and comp_w <= 18 and comp_h <= 18
            color = yellow if is_star else white
            for px, py, a in points:
                if a > 96:
                    pix[px, py] = color

    return out


def _compass_rose(draw: ImageDraw.ImageDraw, target: RenderTarget) -> None:
    cx = target.width - 38
    cy = 38
    r = 24
    white = INKY_PALETTE["WHITE"]
    yellow = INKY_PALETTE["YELLOW"]
    black = INKY_PALETTE["BLACK"]
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=white, width=2)
    draw.polygon((cx, cy - r + 4, cx - 6, cy + 2, cx, cy - 3, cx + 6, cy + 2), fill=yellow)
    draw.line((cx, cy + 4, cx, cy + r - 5), fill=white, width=2)
    draw.line((cx - r + 5, cy, cx + r - 5, cy), fill=white, width=2)
    font = _font(13, bold=True)
    draw.rectangle((cx - 6, cy - r - 15, cx + 7, cy - r - 1), fill=black)
    draw.text((cx - 5, cy - r - 17), "N", fill=white, font=font)


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
    style = PlotStyle().extend(extensions.BLUE_NIGHT)
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

    fitted = _black_yellow_white_chart(img, target)
    draw = ImageDraw.Draw(fitted)
    _compass_rose(draw, target)
    return _finalize(fitted)


def render_mandelbrot(target: RenderTarget, *, seed: str, palette: str = "midnight") -> bytes:
    rng = random.Random(seed)
    cx = -0.745 + rng.uniform(-0.035, 0.035)
    cy = 0.115 + rng.uniform(-0.035, 0.035)
    zoom = rng.uniform(0.9, 1.8)
    span_x = 3.0 / zoom
    span_y = span_x * target.height / target.width
    max_iter = 72
    img = Image.new("RGB", (target.width, target.height), INKY_PALETTE["BLUE"])
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
    img = Image.new("RGB", (target.width, target.height), INKY_PALETTE["YELLOW"])
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
    img = Image.new("RGB", (target.width, target.height), INKY_PALETTE["GREEN"])
    draw = ImageDraw.Draw(img)
    lat = latitude or 0.0
    lon = longitude or 0.0
    phase = observed_at.timetuple().tm_yday / 365 * math.tau
    colors = [INKY_PALETTE[c] for c in ("BLUE", "GREEN", "BLACK", "RED")]
    step = max(24, min(target.width, target.height) // 10)

    for y in range(0, target.height, 18):
        shade = INKY_PALETTE["YELLOW"] if (y // 18) % 2 == 0 else INKY_PALETTE["WHITE"]
        draw.rectangle((0, y, target.width, min(target.height, y + 18)), fill=shade)

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
