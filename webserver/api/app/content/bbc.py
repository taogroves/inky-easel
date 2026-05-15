"""Fetch BBC headlines from one of their RSS feeds."""

from __future__ import annotations

import httpx
import feedparser

DEFAULT_FEED = "https://feeds.bbci.co.uk/news/rss.xml"


async def fetch_bbc(feed_url: str | None = None, limit: int = 4) -> list[dict]:
    url = feed_url or DEFAULT_FEED
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers={"User-Agent": "InkyEasel/1.0"})
        resp.raise_for_status()
        body = resp.text

    parsed = feedparser.parse(body)
    items: list[dict] = []
    for entry in parsed.entries[:limit]:
        items.append({
            "title": getattr(entry, "title", ""),
            "description": getattr(entry, "summary", ""),
            "link": getattr(entry, "link", ""),
        })
    return items
