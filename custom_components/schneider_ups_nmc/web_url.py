"""NMC web URL normalization helpers."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

WEB_URL_SCHEMES = {"http", "https"}


def normalize_web_url(value: Any) -> str | None:
    """Return a normalized HTTP(S) URL for the NMC web UI."""
    if value is None:
        return None

    web_url = str(value).strip()
    if not web_url:
        return None

    if any(char.isspace() for char in web_url):
        raise ValueError

    if "://" not in web_url:
        web_url = f"https://{web_url}"

    parsed = urlparse(web_url)
    if parsed.scheme not in WEB_URL_SCHEMES or not parsed.netloc:
        raise ValueError
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError
    try:
        _ = parsed.port
    except ValueError as err:
        raise ValueError from err
    if parsed.hostname is None:
        raise ValueError

    return web_url
