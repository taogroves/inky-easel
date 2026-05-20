"""Fetch headlines from a user-provided RSS feed."""

from __future__ import annotations

import re
from html import unescape

import feedparser
import httpx

from .url_clean import pick_shortest_url

DEFAULT_FEED = "https://feeds.bbci.co.uk/news/rss.xml"
DEFAULT_TITLE = "BBC News"
DEFAULT_LIMIT = 2


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(unescape(text).split())


def _qr_payload(entry) -> str:
    link = getattr(entry, "link", "") or ""
    guid = str(getattr(entry, "id", "") or getattr(entry, "guid", "") or "").strip()
    return pick_shortest_url(link, guid)


async def fetch_feed_url(
    feed_url: str,
    *,
    limit: int = DEFAULT_LIMIT,
    default_title: str = DEFAULT_TITLE,
) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(feed_url, headers={"User-Agent": "InkyEasel/1.0"})
        resp.raise_for_status()
        body = resp.text

    parsed = feedparser.parse(body)
    feed_title = (
        getattr(parsed.feed, "title", None)
        or getattr(parsed.feed, "description", None)
        or default_title
    )
    feed_title = _strip_html(str(feed_title)) or default_title

    items: list[dict] = []
    for entry in parsed.entries[:limit]:
        author = _strip_html(getattr(entry, "author", "") or "")
        description = _strip_html(getattr(entry, "summary", "") or getattr(entry, "description", "") or "")
        items.append({
            "title": _strip_html(getattr(entry, "title", "") or ""),
            "description": description,
            "author": author,
            "link": getattr(entry, "link", "") or "",
            "guid": _qr_payload(entry),
        })
    return {"title": feed_title, "items": items}


async def fetch_rss(
    feed_url: str | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
) -> dict:
    url = (feed_url or DEFAULT_FEED).strip()
    return await fetch_feed_url(url, limit=limit, default_title=DEFAULT_TITLE)
