"""Normalize article URLs so QR codes stay small and scannable."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_QUERY_KEYS = frozenset({
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "gbraid",
    "wbraid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "mkt_tok",
    "_hsenc",
    "_hsmi",
    "igshid",
    "ocid",
    "ref",
    "ref_src",
    "ref_url",
    "cmpid",
    "cid",
    "campaignid",
    "adgroupid",
    "smid",
    "smtyp",
    "s_cid",
    "at_campaign",
    "at_medium",
    "at_platform",
    "at_bbc_team",
    "at_ptr_type",
    "at_link_origin",
    "at_link_type",
    "at_format",
    "at_campaign_type",
    "at_nation",
    "at_audience_id",
    "at_product",
})


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered in TRACKING_QUERY_KEYS or lowered.startswith("utm_")


def clean_url_for_qr(url: str) -> str:
    """Drop tracking query params and fragments to shorten QR payloads."""
    raw = (url or "").strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        return raw

    parsed = urlparse(raw)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # Reddit RSS permalinks are already short; drop redundant title slug when present.
    path = parsed.path
    if netloc.endswith("reddit.com") and "/comments/" in path:
        parts = [p for p in path.split("/") if p]
        try:
            idx = parts.index("comments")
            if idx + 1 < len(parts) and len(parts) > idx + 2:
                path = "/" + "/".join(parts[: idx + 2]) + "/"
        except ValueError:
            pass

    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not _is_tracking_param(key)
    ]
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        path,
        "",
        urlencode(query, doseq=True),
        "",
    ))


def pick_shortest_url(*urls: str) -> str:
    """Prefer the shortest cleaned HTTP(S) URL for QR encoding."""
    candidates: list[str] = []
    for url in urls:
        if not url:
            continue
        cleaned = clean_url_for_qr(url)
        if cleaned.startswith(("http://", "https://")):
            candidates.append(cleaned)
    if not candidates:
        for url in urls:
            if url:
                return clean_url_for_qr(url)
        return ""
    return min(candidates, key=len)
