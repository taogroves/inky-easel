"""Best-effort link preview extraction for inbox link messages."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

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


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


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
