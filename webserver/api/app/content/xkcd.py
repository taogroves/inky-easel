"""Fetch the latest XKCD comic."""

from __future__ import annotations

import httpx


async def fetch_xkcd() -> dict:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        meta = await client.get("https://xkcd.com/info.0.json")
        meta.raise_for_status()
        meta_json = meta.json()
        img_url = meta_json.get("img")
        img = await client.get(img_url)
        img.raise_for_status()
        return {
            "title": meta_json.get("title", ""),
            "alt": meta_json.get("alt", ""),
            "img_bytes": img.content,
            "num": meta_json.get("num"),
        }
