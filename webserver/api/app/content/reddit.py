"""Fetch posts from a Reddit subreddit via its public RSS feed."""

from __future__ import annotations

import re

from .rss import DEFAULT_LIMIT, _strip_html, fetch_feed_url
from .url_clean import pick_shortest_url

REDDIT_ORANGE = (255, 69, 0)
DEFAULT_SUBREDDIT = "news"
FRONT_PAGE_ALIASES = frozenset({"", "front", "frontpage", "home", "popular"})


def normalize_subreddit(name: str | None) -> str | None:
    if name is None:
        return None
    raw = str(name).strip()
    if not raw:
        return None
    lowered = raw.lower()
    if lowered in FRONT_PAGE_ALIASES:
        return None
    if lowered.startswith("/r/"):
        raw = raw[3:]
    elif lowered.startswith("r/"):
        raw = raw[2:]
    slug = raw.strip("/").split("/")[0]
    if not slug or slug.lower() in FRONT_PAGE_ALIASES:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_]+", slug):
        raise ValueError(f"Invalid subreddit name: {name!r}")
    return slug


def feed_url_for_subreddit(name: str | None) -> str:
    sub = normalize_subreddit(name)
    if sub is None:
        return "https://www.reddit.com/.rss"
    return f"https://www.reddit.com/r/{sub}/.rss"


def display_label(subreddit: str | None) -> str:
    sub = normalize_subreddit(subreddit)
    if sub is None:
        return "Reddit front page"
    return f"r/{sub}"


async def fetch_reddit(
    subreddit: str | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
) -> dict:
    sub = normalize_subreddit(subreddit if subreddit is not None else DEFAULT_SUBREDDIT)
    url = feed_url_for_subreddit(sub)
    label = display_label(sub)
    payload = await fetch_feed_url(url, limit=limit, default_title=label)

    items: list[dict] = []
    for entry in payload.get("items", []):
        title = entry.get("title", "") or "Untitled"
        desc = entry.get("description", "") or ""
        author = entry.get("author", "") or ""
        if not desc and author:
            desc = author if author.startswith("/u/") else f"by {author}"
        items.append({
            "title": title,
            "description": desc,
            "link": entry.get("link", ""),
            "guid": pick_shortest_url(entry.get("link", ""), entry.get("guid", "")),
        })

    feed_title = _strip_html(payload.get("title", "") or label)
    if sub and not feed_title.lower().startswith("r/"):
        if sub.lower() in feed_title.lower():
            feed_title = label
        else:
            feed_title = label

    return {"title": feed_title, "label": label, "subreddit": sub, "items": items}
