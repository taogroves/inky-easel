"""SD-card network and server configuration for Inky Easel frames."""

import json

CONFIG_PATH = "/sd/inky_easel_config.json"
MAX_CREDENTIALS = 5


def _default_server_url():
    try:
        from frame_config import SERVER_URL

        return SERVER_URL
    except ImportError:
        return ""


def _legacy_credentials():
    try:
        from secrets import WIFI_PASSWORD, WIFI_SSID

        if WIFI_SSID:
            return [{"ssid": WIFI_SSID, "password": WIFI_PASSWORD}]
    except ImportError:
        pass
    return []


def _clean_credential(item):
    if not isinstance(item, dict):
        return None
    ssid = str(item.get("ssid") or "").strip()
    if not ssid:
        return None
    password = str(item.get("password") or "")
    return {"ssid": ssid, "password": password}


def _clean_config(data):
    if not isinstance(data, dict):
        data = {}
    credentials = []
    for item in data.get("wifi_credentials") or data.get("credentials") or []:
        cleaned = _clean_credential(item)
        if cleaned:
            credentials.append(cleaned)
        if len(credentials) >= MAX_CREDENTIALS:
            break
    if not credentials:
        credentials = _legacy_credentials()

    active = int(data.get("active_wifi_index") or 0)
    if active < 0 or active >= len(credentials):
        active = 0

    server_url = str(data.get("server_url") or _default_server_url()).strip().rstrip("/")
    return {
        "wifi_credentials": credentials[:MAX_CREDENTIALS],
        "active_wifi_index": active,
        "server_url": server_url,
    }


def load():
    try:
        with open(CONFIG_PATH, "r") as f:
            return _clean_config(json.loads(f.read()))
    except (OSError, ValueError):
        return _clean_config({})


def save(config):
    data = _clean_config(config)
    with open(CONFIG_PATH, "w") as f:
        f.write(json.dumps(data))
        f.flush()
    return data


def get_credentials():
    return load().get("wifi_credentials") or []


def get_active_credential():
    config = load()
    credentials = config.get("wifi_credentials") or []
    if not credentials:
        return None
    idx = int(config.get("active_wifi_index") or 0)
    if idx < 0 or idx >= len(credentials):
        idx = 0
    return credentials[idx]


def get_server_url():
    return load().get("server_url") or _default_server_url()


def set_active_wifi_index(index):
    config = load()
    credentials = config.get("wifi_credentials") or []
    if not credentials:
        return config
    index = max(0, min(int(index), len(credentials) - 1))
    config["active_wifi_index"] = index
    return save(config)


def update(server_url=None, wifi_credentials=None, active_wifi_index=None):
    config = load()
    if server_url is not None:
        config["server_url"] = str(server_url).strip().rstrip("/")
    if wifi_credentials is not None:
        config["wifi_credentials"] = wifi_credentials
    if active_wifi_index is not None:
        config["active_wifi_index"] = int(active_wifi_index)
    return save(config)
