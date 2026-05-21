"""Talk to the webserver: poll for the next item, stream JPEG content to SD,
and run user-defined plugins. Designed for the very tight Pico RAM budget.

Protocol (POST /api/frame/poll):

  request  = { "frame_id": str, "secret": str,
               "battery_voltage": float, "battery_percent": int,
               "wakeup": "rtc"|"button"|"power",
               "has_sd_card": bool }

  response = { "type": "image"|"text"|"plugin"|"sleep",
               "image_url": str | null,
               "image_mime": str | null,
               "text": { "title": str, "body": str, "accent": str } | null,
               "plugin": { "code": str, "context": dict } | null,
               "sleep_minutes": int,
               "low_battery_warning": bool }
"""

import gc
import json
import os

try:
    import socket
except ImportError:
    socket = None

try:
    from urllib import urequest as _urequest
except ImportError:
    import urequest as _urequest

CONTENT_PATH = "/sd/_content.jpg"
PLUGIN_PATH = "/sd/_plugin.py"


def content_path_for(mime=None, *, on_sd=True):
    base = "/sd/_content" if on_sd else "/_content"
    if mime == "image/png":
        return base + ".png"
    return base + ".jpg"
HTTP_TIMEOUT_SECONDS = 20


def _content_path():
    return CONTENT_PATH


def _plugin_path():
    return PLUGIN_PATH


class PollError(Exception):
    pass


def _to_text(raw):
    if hasattr(raw, "decode"):
        return raw.decode("utf-8")
    return raw


def _preview(text, limit=120):
    text = str(text).replace("\r", " ").replace("\n", " ").strip()
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def _set_timeout():
    if socket and hasattr(socket, "setdefaulttimeout"):
        socket.setdefaulttimeout(HTTP_TIMEOUT_SECONDS)


def _http_post_json(url, payload):
    body = json.dumps(payload).encode("utf-8")
    print("POST", url)
    _set_timeout()
    sock = _urequest.urlopen(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        raw = sock.read()
    finally:
        sock.close()
    gc.collect()

    status = getattr(sock, "status", None) or getattr(sock, "status_code", None)
    text = _to_text(raw)
    if status and status >= 400:
        raise PollError("HTTP {}: {}".format(status, _preview(text)))
    try:
        return json.loads(text)
    except Exception as e:
        raise PollError("Bad JSON: {} ({})".format(_preview(text), e))


def poll(server_url, frame_id, secret, battery_voltage, battery_percent, wakeup, has_sd_card=False):
    url = server_url.rstrip("/") + "/api/frame/poll"
    payload = {
        "frame_id": frame_id,
        "secret": secret,
        "server_url": server_url.rstrip("/"),
        "battery_voltage": round(battery_voltage, 3),
        "battery_percent": battery_percent,
        "wakeup": wakeup,
        "has_sd_card": bool(has_sd_card),
    }
    try:
        return _http_post_json(url, payload)
    except PollError:
        raise
    except Exception as e:
        raise PollError(str(e))


def download_image(url, dest=None, mime=None):
    if dest is None:
        dest = _content_path()
    print("GET", url)
    _set_timeout()
    sock = _urequest.urlopen(url)
    try:
        chunk = bytearray(1024)
        try:
            os.remove(dest)
        except OSError:
            pass
        with open(dest, "wb") as f:
            while True:
                n = sock.readinto(chunk)
                if not n:
                    break
                if n == len(chunk):
                    f.write(chunk)
                else:
                    f.write(chunk[:n])
        return dest
    finally:
        sock.close()
        gc.collect()


def download_jpeg(url, dest=None, mime=None):
    """Backward-compatible alias for download_image."""
    return download_image(url, dest=dest, mime=mime)


def render_image(graphics, path=None, mime=None):
    if path is None:
        path = _content_path()
    use_png = mime == "image/png" or str(path).lower().endswith(".png")
    if use_png:
        from pngdec import PNG

        png = PNG(graphics)
        png.open_file(path)
        png.decode(0, 0)
        return
    import jpegdec

    jpeg = jpegdec.JPEG(graphics)
    jpeg.open_file(path)
    jpeg.decode()


def run_plugin(graphics, width, height, code, context):
    """Persist user code then import it so MicroPython compiles it once.

    Plugins must define `draw(graphics, width, height, context)`. We import via
    a fresh module name each time by deleting any cached entry first.
    """
    plugin_path = _plugin_path()
    with open(plugin_path, "w") as f:
        f.write(code)

    sys_mod = __import__("sys")
    if "_plugin" in sys_mod.modules:
        del sys_mod.modules["_plugin"]

    plugin_dir = os.path.dirname(plugin_path) or "/"
    added_path = plugin_dir not in sys_mod.path
    if added_path:
        sys_mod.path.insert(0, plugin_dir)

    try:
        plugin = __import__("_plugin")
        if not hasattr(plugin, "draw"):
            raise RuntimeError("plugin missing draw(graphics, width, height, context)")
        plugin.draw(graphics, width, height, context or {})
    finally:
        if added_path and plugin_dir in sys_mod.path:
            sys_mod.path.remove(plugin_dir)
        if "_plugin" in sys_mod.modules:
            del sys_mod.modules["_plugin"]
        try:
            os.remove(plugin_path)
        except OSError:
            pass
        gc.collect()
