"""Fetch weather from Open-Meteo (no API key required)."""

from __future__ import annotations

from datetime import datetime

import httpx

_WMO_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Light rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Heavy showers",
    82: "Violent showers",
    95: "Thunderstorm",
    96: "Thunderstorm w/ hail",
    99: "Thunderstorm w/ heavy hail",
}


def _format_time(iso_value: str | None) -> str | None:
    if not iso_value:
        return None
    try:
        return datetime.fromisoformat(iso_value.replace("Z", "+00:00")).strftime("%H:%M")
    except ValueError:
        if "T" in iso_value:
            return iso_value.split("T", 1)[1][:5]
        return iso_value[:5]


def _normalize_units(units: str | None) -> str:
    if units and units.lower() in {"f", "fahrenheit", "imperial"}:
        return "fahrenheit"
    return "celsius"


async def fetch_weather(
    latitude: float,
    longitude: float,
    timezone: str | None = None,
    units: str | None = None,
) -> dict:
    unit = _normalize_units(units)
    use_fahrenheit = unit == "fahrenheit"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,precipitation_probability,wind_speed_10m",
        "daily": "sunrise,sunset",
        "timezone": timezone or "auto",
        "forecast_days": 1,
        "temperature_unit": "fahrenheit" if use_fahrenheit else "celsius",
        "wind_speed_unit": "mph" if use_fahrenheit else "kmh",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
        resp.raise_for_status()
        data = resp.json()

    current_block = data.get("current", {})
    code = current_block.get("weather_code", 0)
    current = {
        "temperature": current_block.get("temperature_2m", 0),
        "humidity": current_block.get("relative_humidity_2m", 0),
        "wind_speed": current_block.get("wind_speed_10m", 0),
        "code": code,
        "description": _WMO_DESCRIPTIONS.get(code, "Unknown"),
    }

    hourly_block = data.get("hourly", {}) or {}
    times = hourly_block.get("time", [])
    temps = hourly_block.get("temperature_2m", [])
    precip = hourly_block.get("precipitation_probability", [])
    winds = hourly_block.get("wind_speed_10m", [])
    hourly: list[dict] = []
    for i, when in enumerate(times):
        try:
            hour_label = datetime.fromisoformat(when).strftime("%H")
        except ValueError:
            hour_label = when[-5:-3] if len(when) >= 5 else ""
        hourly.append({
            "time": when,
            "hour": hour_label,
            "temperature": temps[i] if i < len(temps) else None,
            "precip_prob": precip[i] if i < len(precip) else None,
            "wind_speed": winds[i] if i < len(winds) else None,
        })

    daily = data.get("daily", {}) or {}
    sunrise = _format_time((daily.get("sunrise") or [None])[0])
    sunset = _format_time((daily.get("sunset") or [None])[0])

    return {
        "current": current,
        "hourly": hourly,
        "sunrise": sunrise,
        "sunset": sunset,
        "units": unit,
        "wind_unit": "mph" if use_fahrenheit else "km/h",
        "timezone": data.get("timezone"),
    }
