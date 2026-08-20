"""Per-host adapters for fetching hotlink-protected remote images.

Mirrors the ordering Strategy pattern (collector/ordering.py): each host
that needs special handling gets its own adapter; hosts with no adapter
fall through to a generic one that sets a parent-domain Referer.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Protocol


class HostAdapter(Protocol):
    def matches(self, url: str) -> bool: ...

    def fetch_target(self, url: str) -> tuple[str, str]:
        """Returns (url_to_fetch, referer)."""
        ...


class ImgurAdapter:
    """i.imgur.com direct links resolve to an HTML "removed" page (status
    200, not 404) unless routed through Imgur's download endpoint with a
    Referer from the image's own page."""

    _DIRECT = re.compile(r"^https?://i\.imgur\.com/([A-Za-z0-9]+)(?:\.\w+)?$")

    def matches(self, url: str) -> bool:
        return bool(self._DIRECT.match(url))

    def fetch_target(self, url: str) -> tuple[str, str]:
        image_id = self._DIRECT.match(url).group(1)
        return (
            f"https://imgur.com/download/{image_id}/",
            f"https://imgur.com/{image_id}",
        )


class GenericAdapter:
    """Fallback for hosts with no dedicated adapter: leave the URL as-is
    and set a Referer from the parent domain, since hotlink protection
    commonly trusts same-site Referers (e.g. a CDN subdomain trusting
    requests referred from its own root domain)."""

    def matches(self, url: str) -> bool:
        return True

    def fetch_target(self, url: str) -> tuple[str, str]:
        netloc = urllib.parse.urlparse(url).netloc
        parts = netloc.split(".")
        parent = ".".join(parts[1:]) if len(parts) > 2 else netloc
        return url, f"https://{parent}/"


_ADAPTERS: list[HostAdapter] = [ImgurAdapter()]
_DEFAULT_ADAPTER: HostAdapter = GenericAdapter()


def resolve_fetch_target(url: str) -> tuple[str, str]:
    """Returns (url_to_fetch, referer) for the first matching adapter, or
    the generic adapter's result when no host-specific adapter applies."""
    for adapter in _ADAPTERS:
        if adapter.matches(url):
            return adapter.fetch_target(url)
    return _DEFAULT_ADAPTER.fetch_target(url)
