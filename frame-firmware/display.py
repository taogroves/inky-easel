"""Display helpers: pen palette, battery overlay, fullscreen empty-battery scene,
and simple text wrapping for text-type content.
"""

import inky_frame

WHITE = inky_frame.WHITE
BLACK = inky_frame.BLACK
RED = inky_frame.RED
ORANGE = inky_frame.ORANGE
YELLOW = inky_frame.YELLOW
GREEN = inky_frame.GREEN
BLUE = inky_frame.BLUE


def clear(graphics, color=WHITE):
    graphics.set_pen(color)
    graphics.clear()


def draw_battery_overlay(graphics, width, percent, charging=False):
    """Compact battery icon in top-right with percent and charging state."""
    body_w = 82
    body_h = 28
    tip_w = 6
    tip_h = 12
    pad = 12
    x = width - body_w - tip_w - pad
    y = pad

    graphics.set_pen(WHITE)
    graphics.rectangle(x - 2, y - 2, body_w + tip_w + 4, body_h + 4)
    graphics.set_pen(BLACK)
    graphics.rectangle(x, y, body_w, body_h)
    graphics.set_pen(WHITE)
    graphics.rectangle(x + 2, y + 2, body_w - 4, body_h - 4)
    graphics.set_pen(BLACK)
    graphics.rectangle(x + body_w, y + (body_h - tip_h) // 2, tip_w, tip_h)

    fill_w = max(2, int((body_w - 8) * max(0, min(100, percent)) / 100))
    graphics.set_pen(RED)
    graphics.rectangle(x + 4, y + 4, fill_w, body_h - 8)

    graphics.set_pen(BLACK)
    label = "{}%".format(percent)
    label_scale = 2
    if charging and len(label) > 3:
        label_scale = 1
    graphics.set_font("bitmap8")
    label_w = graphics.measure_text(label, label_scale)
    if charging:
        _draw_lightning_bolt(graphics, x + 8, y + 5)
        text_x = x + 28 + max(0, (body_w - 30 - label_w) // 2)
        text_y = y + 6 if label_scale == 2 else y + 10
    else:
        text_x = x + max(0, (body_w - label_w) // 2)
        text_y = y + 6
    graphics.text(label, text_x, text_y, body_w - 4, label_scale)


def draw_low_battery_overlay(graphics, width, percent):
    draw_battery_overlay(graphics, width, percent, charging=False)


def _draw_lightning_bolt(graphics, x, y):
    # Drawn as chunky rectangles so it works on PicoGraphics without polygons.
    graphics.rectangle(x + 7, y, 5, 9)
    graphics.rectangle(x + 4, y + 7, 7, 5)
    graphics.rectangle(x + 1, y + 11, 6, 4)
    graphics.rectangle(x + 5, y + 12, 5, 9)


def draw_critical_battery_screen(graphics, width, height):
    """Fullscreen "plug me in" screen shown when battery is critical."""
    graphics.set_pen(WHITE)
    graphics.clear()

    graphics.set_pen(RED)
    graphics.rectangle(0, 0, width, 60)
    graphics.set_pen(WHITE)
    graphics.set_font("bitmap8")
    title = "BATTERY CRITICAL"
    title_w = graphics.measure_text(title, 4)
    graphics.text(title, (width - title_w) // 2, 16, width, 4)

    cx = width // 2
    cy = height // 2
    bw = 280
    bh = 120
    tw = 24
    th = 50

    graphics.set_pen(BLACK)
    graphics.rectangle(cx - bw // 2, cy - bh // 2, bw, bh)
    graphics.set_pen(WHITE)
    graphics.rectangle(cx - bw // 2 + 6, cy - bh // 2 + 6, bw - 12, bh - 12)
    graphics.set_pen(BLACK)
    graphics.rectangle(cx + bw // 2, cy - th // 2, tw, th)

    graphics.set_pen(RED)
    graphics.rectangle(cx - bw // 2 + 12, cy - bh // 2 + 12, 20, bh - 24)

    graphics.set_pen(BLACK)
    msg = "Plug me in - sleeping for 1 hour"
    msg_w = graphics.measure_text(msg, 3)
    graphics.text(msg, (width - msg_w) // 2, height - 80, width, 3)

    graphics.update()


def draw_text_content(graphics, width, height, title, body, accent=BLUE):
    """Render a text payload: colored title bar over wrapped body."""
    graphics.set_pen(WHITE)
    graphics.clear()
    graphics.set_font("bitmap8")

    if title:
        graphics.set_pen(accent)
        graphics.rectangle(0, 0, width, 56)
        graphics.set_pen(WHITE)
        graphics.text(title, 16, 16, width - 32, 3)

    graphics.set_pen(BLACK)
    _wrap_text(graphics, body or "", 24, 80, width - 48, 3, 4)


def draw_error_screen(graphics, width, height, message):
    graphics.set_pen(WHITE)
    graphics.clear()
    graphics.set_pen(RED)
    graphics.rectangle(0, height // 2 - 24, width, 48)
    graphics.set_pen(WHITE)
    graphics.set_font("bitmap8")
    msg_w = graphics.measure_text(message, 3)
    graphics.text(message, (width - msg_w) // 2, height // 2 - 12, width, 3)


def _wrap_text(graphics, text, x, y, max_w, scale, spacing):
    if not text:
        return
    line_h = 8 * scale + spacing
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        line = ""
        for word in words:
            candidate = (line + " " + word).strip()
            if graphics.measure_text(candidate, scale) <= max_w:
                line = candidate
            else:
                graphics.text(line, x, y, max_w, scale)
                y += line_h
                line = word
        if line:
            graphics.text(line, x, y, max_w, scale)
            y += line_h
        y += spacing
