"""Best-effort link preview extraction for inbox link messages."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

import feedparser
import httpx

from .rss import _strip_html
from .url_clean import clean_url_for_qr

MAX_LINK_BYTES = 6 * 1024 * 1024
MAX_HTML_BYTES = 750 * 1024


@dataclass
class LinkPreview:
    url: str
    final_url: str
    domain: str
    title: str | None = None
    description: str | None = None
    image_url: str | None = None
    image_bytes: bytes | None = None
    image_mime: str | None = None
    is_direct_image: bool = False


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self._in_title = False
        self._title_parts: list[str] = []
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() == "title":
            self._in_title = True
            return
        if tag.lower() != "meta":
            return
        data = {str(k).lower(): str(v) for k, v in attrs if k and v}
        key = (data.get("property") or data.get("name") or "").lower()
        content = data.get("content")
        if key and content and key not in self.meta:
            self.meta[key] = " ".join(content.split())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
            title = " ".join("".join(self._title_parts).split())
            if title:
                self.title = title

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)


class _FirstImageParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.image_url: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        if self.image_url or tag.lower() != "img":
            return
        data = {str(k).lower(): str(v) for k, v in attrs if k and v}
        src = data.get("src")
        if src:
            self.image_url = clean_url_for_qr(urljoin(self.base_url, unescape(src)))


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _is_reddit_url(url: str) -> bool:
    return urlparse(url).netloc.lower().endswith("reddit.com")


def _is_reddit_verification_title(title: str | None) -> bool:
    return bool(title and "wait for verification" in title.lower())


def _absolute_url(base: str, maybe_url: str | None) -> str | None:
    if not maybe_url:
        return None
    return clean_url_for_qr(urljoin(base, maybe_url.strip()))


def _content_type(headers: httpx.Headers) -> str:
    return headers.get("content-type", "").split(";", 1)[0].strip().lower()


def _reddit_json_url(url: str) -> str | None:
    parsed = urlparse(url)
    if not parsed.netloc.lower().endswith("reddit.com"):
        return None
    parts = [part for part in parsed.path.split("/") if part]
    try:
        r_idx = parts.index("r")
        comments_idx = parts.index("comments")
    except ValueError:
        return None
    if r_idx + 1 >= len(parts) or comments_idx + 1 >= len(parts):
        return None
    sub = parts[r_idx + 1]
    post_id = parts[comments_idx + 1]
    return f"https://www.reddit.com/r/{sub}/comments/{post_id}/.json?raw_json=1"


def _reddit_rss_url(url: str) -> str | None:
    parsed = urlparse(url)
    if not parsed.netloc.lower().endswith("reddit.com"):
        return None
    path = parsed.path.rstrip("/")
    if not path:
        return "http://www.reddit.com/.rss"
    if path.endswith(".rss"):
        return f"http://www.reddit.com{path}"
    return f"http://www.reddit.com{path}/.rss"


async def _read_limited(resp: httpx.Response, limit: int) -> bytes:
    data = bytearray()
    async for chunk in resp.aiter_bytes():
        data.extend(chunk)
        if len(data) > limit:
            raise ValueError("Response body is too large")
    return bytes(data)


async def _fetch_bytes(client: httpx.AsyncClient, url: str, limit: int) -> tuple[bytes, str, str]:
    async with client.stream("GET", url) as resp:
        resp.raise_for_status()
        data = await _read_limited(resp, limit)
        return data, _content_type(resp.headers), clean_url_for_qr(str(resp.url))


def _fetch_reddit_rss_sync(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; InkyEasel/1.0; +https://inky-easel.local)",
            "Accept": "application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.5",
        },
    )
    with urlopen(req, timeout=12) as resp:
        body = resp.read(MAX_HTML_BYTES + 1)
    if len(body) > MAX_HTML_BYTES:
        body = body[:MAX_HTML_BYTES]
    return body.decode("utf-8", errors="replace")


def _entry_image_url(entry, base_url: str) -> str | None:
    for attr in ("media_thumbnail", "media_content"):
        media = getattr(entry, attr, None)
        if media:
            for item in media:
                url = item.get("url") if isinstance(item, dict) else None
                if url:
                    return clean_url_for_qr(unescape(url))

    for link in getattr(entry, "links", []) or []:
        rel = (link.get("rel") or "").lower()
        mime = (link.get("type") or "").lower()
        href = link.get("href")
        if href and (rel == "enclosure" or mime.startswith("image/")):
            return clean_url_for_qr(unescape(href))

    summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    parser = _FirstImageParser(base_url)
    parser.feed(summary)
    return parser.image_url


async def _try_reddit_rss_preview(client: httpx.AsyncClient, url: str) -> LinkPreview | None:
    rss_url = _reddit_rss_url(url)
    if not rss_url:
        return None

    body = await asyncio.to_thread(_fetch_reddit_rss_sync, rss_url)
    parsed = feedparser.parse(body)
    entries = list(getattr(parsed, "entries", []) or [])
    if not entries:
        return None

    clean_original = clean_url_for_qr(url)
    original_path = urlparse(clean_original).path.rstrip("/")
    entry = entries[0]
    if "/comments/" in original_path:
        for candidate in entries:
            candidate_link = clean_url_for_qr(getattr(candidate, "link", "") or "")
            if original_path and original_path in urlparse(candidate_link).path.rstrip("/"):
                entry = candidate
                break

    title = _strip_html(getattr(entry, "title", "") or "")
    description = _strip_html(getattr(entry, "summary", "") or getattr(entry, "description", "") or "")
    link = clean_url_for_qr(getattr(entry, "link", "") or clean_original)
    if not title or _is_reddit_verification_title(title):
        return None

    preview = LinkPreview(
        url=clean_original,
        final_url=link or clean_original,
        domain="reddit.com",
        title=title,
        description=description,
    )
    preview.image_url = _entry_image_url(entry, preview.final_url)
    if preview.image_url:
        try:
            image_body, image_mime, _ = await _fetch_bytes(client, preview.image_url, MAX_LINK_BYTES)
            if image_mime.startswith("image/"):
                preview.image_bytes = image_body
                preview.image_mime = image_mime
        except Exception:
            pass
    return preview


async def _try_reddit_preview(client: httpx.AsyncClient, url: str) -> LinkPreview | None:
    json_url = _reddit_json_url(url)
    if not json_url:
        return None
    resp = await client.get(json_url, headers={"Accept": "application/json"})
    resp.raise_for_status()
    data = resp.json()
    post = data[0]["data"]["children"][0]["data"]
    final_url = clean_url_for_qr(url)
    preview = LinkPreview(
        url=final_url,
        final_url=final_url,
        domain="reddit.com",
        title=post.get("title"),
        description=(post.get("selftext") or post.get("subreddit_name_prefixed") or "").strip(),
    )
    image_url = post.get("url_overridden_by_dest")
    if not image_url:
        images = (((post.get("preview") or {}).get("images") or []))
        if images:
            image_url = ((images[0].get("source") or {}).get("url"))
    preview.image_url = clean_url_for_qr(unescape(image_url or "")) or None
    if preview.image_url:
        try:
            image_body, image_mime, _ = await _fetch_bytes(client, preview.image_url, MAX_LINK_BYTES)
            if image_mime.startswith("image/"):
                preview.image_bytes = image_body
                preview.image_mime = image_mime
        except Exception:
            pass
    return preview


async def resolve_link_preview(url: str) -> LinkPreview:
    cleaned = clean_url_for_qr(url)
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Link must be an http(s) URL")

    headers = {
        "User-Agent": "InkyEasel/1.0 (+https://inky-easel.local)",
        "Accept": "text/html,application/xhtml+xml,image/*;q=0.9,*/*;q=0.5",
    }
    async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers=headers) as client:
        try:
            reddit_rss_preview = await _try_reddit_rss_preview(client, cleaned)
            if reddit_rss_preview:
                return reddit_rss_preview
        except Exception:
            pass

        try:
            reddit_preview = await _try_reddit_preview(client, cleaned)
            if reddit_preview:
                return reddit_preview
        except Exception:
            pass

        body, mime, final_url = await _fetch_bytes(client, cleaned, MAX_LINK_BYTES)
        final_url = clean_url_for_qr(final_url)
        preview = LinkPreview(url=cleaned, final_url=final_url, domain=_domain(final_url))

        if mime.startswith("image/"):
            preview.image_bytes = body
            preview.image_mime = mime
            preview.is_direct_image = True
            return preview

        if mime not in {"text/html", "application/xhtml+xml"}:
            return preview

        html = body[:MAX_HTML_BYTES].decode("utf-8", errors="replace")
        parser = _MetadataParser()
        parser.feed(html)
        meta = parser.meta
        preview.title = meta.get("og:title") or meta.get("twitter:title") or parser.title
        preview.description = (
            meta.get("og:description")
            or meta.get("twitter:description")
            or meta.get("description")
        )
        if _is_reddit_url(final_url) and _is_reddit_verification_title(preview.title):
            preview.title = None
            preview.description = None
            preview.image_url = None
            return preview
        preview.image_url = _absolute_url(
            final_url,
            meta.get("og:image") or meta.get("twitter:image") or meta.get("twitter:image:src"),
        )

        if preview.image_url:
            try:
                image_body, image_mime, _ = await _fetch_bytes(client, preview.image_url, MAX_LINK_BYTES)
                if image_mime.startswith("image/"):
                    preview.image_bytes = image_body
                    preview.image_mime = image_mime
            except Exception:
                preview.image_bytes = None
                preview.image_mime = None

        return preview
