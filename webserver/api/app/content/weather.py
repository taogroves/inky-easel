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


async def fetch_weather(latitude: float, longitude: float, timezone: str | None = None) -> dict:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code",
        "timezone": "auto",
        "forecast_days": 4,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get("https://api.open-meteo.com/v1/forecast", params=params)
        resp.raise_for_status()
        data = resp.json()

    current_block = data.get("current", {})
    current = {
        "temperature": current_block.get("temperature_2m", 0),
        "humidity": current_block.get("relative_humidity_2m", 0),
        "wind_speed": current_block.get("wind_speed_10m", 0),
        "code": current_block.get("weather_code", 0),
        "description": _WMO_DESCRIPTIONS.get(current_block.get("weather_code", 0), "Unknown"),
    }

    daily = data.get("daily", {}) or {}
    forecast: list[dict] = []
    for i, day in enumerate(daily.get("time", [])):
        try:
            label = datetime.strptime(day, "%Y-%m-%d").strftime("%a")
        except ValueError:
            label = day
        forecast.append({
            "label": label,
            "high": daily.get("temperature_2m_max", [None])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
            "low": daily.get("temperature_2m_min", [None])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
            "code": daily.get("weather_code", [0])[i] if i < len(daily.get("weather_code", [])) else 0,
        })

    return {"current": current, "forecast": forecast, "timezone": data.get("timezone")}
