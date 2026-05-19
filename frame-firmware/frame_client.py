"""Talk to the webserver: poll for the next item, stream JPEG content to SD,
and run user-defined plugins. Designed for the very tight Pico RAM budget.

Protocol (POST /api/frame/poll):

  request  = { "frame_id": str, "secret": str,
               "battery_voltage": float, "battery_percent": int,
               "wakeup": "rtc"|"button"|"power" }

  response = { "type": "image"|"text"|"plugin"|"sleep",
               "image_url": str | null,
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
HTTP_TIMEOUT_SECONDS = 20


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


def poll(server_url, frame_id, secret, battery_voltage, battery_percent, wakeup):
    url = server_url.rstrip("/") + "/api/frame/poll"
    payload = {
        "frame_id": frame_id,
        "secret": secret,
        "server_url": server_url.rstrip("/"),
        "battery_voltage": round(battery_voltage, 3),
        "battery_percent": battery_percent,
        "wakeup": wakeup,
    }
    try:
        return _http_post_json(url, payload)
    except PollError:
        raise
    except Exception as e:
        raise PollError(str(e))


def download_jpeg(url, dest=CONTENT_PATH):
    print("GET", url)
    _set_timeout()
    sock = _urequest.urlopen(url)
    try:
        chunk = bytearray(1024)
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


def render_image(graphics, path=CONTENT_PATH):
    import jpegdec

    jpeg = jpegdec.JPEG(graphics)
    jpeg.open_file(path)
    jpeg.decode()


def run_plugin(graphics, width, height, code, context):
    """Persist user code to SD then import it so MicroPython compiles it once.

    Plugins must define `draw(graphics, width, height, context)`. We import via
    a fresh module name each time by deleting any cached entry first.
    """
    with open(PLUGIN_PATH, "w") as f:
        f.write(code)

    sys_mod = __import__("sys")
    if "_plugin" in sys_mod.modules:
        del sys_mod.modules["_plugin"]

    sd_in_path = "/sd" in sys_mod.path
    if not sd_in_path:
        sys_mod.path.insert(0, "/sd")

    try:
        plugin = __import__("_plugin")
        if not hasattr(plugin, "draw"):
            raise RuntimeError("plugin missing draw(graphics, width, height, context)")
        plugin.draw(graphics, width, height, context or {})
    finally:
        if not sd_in_path and "/sd" in sys_mod.path:
            sys_mod.path.remove("/sd")
        if "_plugin" in sys_mod.modules:
            del sys_mod.modules["_plugin"]
        try:
            os.remove(PLUGIN_PATH)
        except OSError:
            pass
        gc.collect()
