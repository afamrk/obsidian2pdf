"""Text transforms turning Obsidian syntax into standard Markdown/HTML.

Each transform has one job and the signature apply(text, ctx) -> text.
The pipeline runs them in order with fenced/inline code masked out.
"""
from __future__ import annotations

import hashlib
import html
import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from curl_cffi import requests as curl_requests
from curl_cffi.requests.exceptions import RequestException

from ..vault import IMAGE_EXTS
from .host_adapters import resolve_fetch_target


@dataclass
class NoteContext:
    note_path: Path
    vault_root: Path
    attachments: dict[str, Path]
    ignored_exts: frozenset[str] = frozenset()
    image_cache_dir: Path | None = None
    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        self.warnings.append(f"{self.note_path.name}: {message}")


class Transform(Protocol):
    def apply(self, text: str, ctx: NoteContext) -> str: ...


WIKI_EMBED = re.compile(r"!\[\[([^\]]+)\]\]")
MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
WIKI_LINK = re.compile(r"(?<!!)\[\[([^\]]+)\]\]")
VIDEO_HOSTS = ("youtube.com", "youtu.be", "vimeo.com")


def _target_ext(target: str) -> str:
    path = urllib.parse.urlparse(target.split("|")[0].split("#")[0]).path
    return Path(path).suffix.lstrip(".").lower()


def _missing_embed(name: str) -> str:
    return f'<div class="missing-embed">missing image: {html.escape(name)}</div>'


def _link_label(raw: str) -> str:
    """Obsidian's display text for [[target#section|alias]]: the alias when
    present, else target and section joined by " > " — a same-note
    [[#section]] link shows the section alone."""
    target, _, alias = raw.partition("|")
    if alias.strip():
        return alias.strip()
    note, _, section = target.partition("#")
    return " > ".join(part.strip() for part in (note, section) if part.strip())


class FrontmatterStripper:
    """Remove a leading YAML frontmatter block."""

    _FM = re.compile(r"^---\s*\n.*?\n---\s*\n?", re.DOTALL)

    def apply(self, text: str, ctx: NoteContext) -> str:
        m = self._FM.match(text)
        return text[m.end():] if m else text


class IgnoredMediaFilter:
    """Silently drop embeds whose extension is in ctx.ignored_exts."""

    def apply(self, text: str, ctx: NoteContext) -> str:
        if not ctx.ignored_exts:
            return text

        def drop(match: re.Match, group: int) -> str:
            if _target_ext(match.group(group)) in ctx.ignored_exts:
                return ""
            return match.group(0)

        text = WIKI_EMBED.sub(lambda m: drop(m, 1), text)
        return MD_IMAGE.sub(lambda m: drop(m, 2), text)


class VideoEmbedToLink:
    """![](youtube/vimeo url) -> a styled link (video can't render in PDF)."""

    def apply(self, text: str, ctx: NoteContext) -> str:
        def repl(m: re.Match) -> str:
            url = m.group(2)
            host = urllib.parse.urlparse(url).netloc.lower()
            host = host.removeprefix("www.")
            if any(host == h or host.endswith("." + h) for h in VIDEO_HOSTS):
                safe = html.escape(url)
                return f'<a class="video-link" href="{safe}">&#9654; {safe}</a>'
            return m.group(0)

        return MD_IMAGE.sub(repl, text)


class ImageEmbedResolver:
    """![[img.png]] -> ![](file:///abs/path) using Obsidian-style resolution:
    path-containing targets resolve against note folder then vault root;
    bare names resolve to a sibling file, then the vault-wide index."""

    def apply(self, text: str, ctx: NoteContext) -> str:
        def repl(m: re.Match) -> str:
            name = m.group(1).split("|")[0].split("#")[0].strip()
            if _target_ext(name) not in IMAGE_EXTS:
                return m.group(0)  # not an image: NoteEmbedToLink handles it
            resolved = self._resolve(name, ctx)
            if resolved is None:
                ctx.warn(f"missing image {name!r}")
                return _missing_embed(name)
            return f"![]({resolved.as_uri()})"

        return WIKI_EMBED.sub(repl, text)

    @staticmethod
    def _resolve(name: str, ctx: NoteContext) -> Path | None:
        if "/" in name:
            for base in (ctx.note_path.parent, ctx.vault_root):
                candidate = (base / name).resolve()
                if candidate.is_file():
                    return candidate
            return None
        sibling = ctx.note_path.parent / name
        if sibling.is_file():
            return sibling
        return ctx.attachments.get(name)


class NoteEmbedToLink:
    """Remaining ![[...]] embeds (notes, blocks, audio) -> styled reference."""

    def apply(self, text: str, ctx: NoteContext) -> str:
        def repl(m: re.Match) -> str:
            raw = m.group(1)
            label = raw.split("|")[-1].split("#")[0].strip() or raw.strip()
            return f'<span class="embed-ref">&#128196; {html.escape(label)}</span>'

        return WIKI_EMBED.sub(repl, text)


class WikilinkToText:
    """[[Target|alias]] -> styled plain text (targets may not be in the PDF)."""

    def apply(self, text: str, ctx: NoteContext) -> str:
        def repl(m: re.Match) -> str:
            label = _link_label(m.group(1))
            return f'<span class="wikilink">{html.escape(label)}</span>'

        return WIKI_LINK.sub(repl, text)


class LocalMdImageResolver:
    """![](relative/path.png) -> absolute file:// URI (notes merge into one
    document, so relative paths would break)."""

    def apply(self, text: str, ctx: NoteContext) -> str:
        def repl(m: re.Match) -> str:
            alt, target = m.group(1), m.group(2)
            if target.startswith(("http://", "https://", "file://", "data:")):
                return m.group(0)
            rel = urllib.parse.unquote(target)
            for base in (ctx.note_path.parent, ctx.vault_root):
                candidate = (base / rel).resolve()
                if candidate.is_file():
                    return f"![{alt}]({candidate.as_uri()})"
            ctx.warn(f"missing image {rel!r}")
            return _missing_embed(rel)

        return MD_IMAGE.sub(repl, text)


class RemoteImageFetcher:
    """Download ![](http...) images so the PDF embeds them; on failure the
    URL is rendered as a link (per spec) with a warning.

    Uses curl_cffi with browser TLS/HTTP impersonation — hosts like Imgur
    rate-limit or block plain urllib requests (429) but accept real browser
    fingerprints. Per-host fetch quirks (URL rewriting, Referer) come from
    host_adapters.resolve_fetch_target. Content-Type is verified too: some
    hotlink-protected hosts return an HTML "not found" page with status 200
    instead of a real 404, which a status check alone wouldn't catch.
    """

    TIMEOUT_S = 20

    def apply(self, text: str, ctx: NoteContext) -> str:
        def repl(m: re.Match) -> str:
            alt, url = m.group(1), m.group(2)
            if not url.startswith(("http://", "https://")):
                return m.group(0)
            local = self._fetch(url, ctx)
            if local is None:
                ctx.warn(f"could not fetch {url}")
                safe = html.escape(url)
                return f'<a href="{safe}">{safe}</a>'
            return f"![{alt}]({local.as_uri()})"

        return MD_IMAGE.sub(repl, text)

    def _fetch(self, url: str, ctx: NoteContext) -> Path | None:
        if ctx.image_cache_dir is None:
            return None
        suffix = Path(urllib.parse.urlparse(url).path).suffix or ".img"
        dest = ctx.image_cache_dir / (
            hashlib.sha1(url.encode()).hexdigest() + suffix
        )
        if dest.is_file():
            return dest
        fetch_url, referer = resolve_fetch_target(url)
        try:
            resp = curl_requests.get(
                fetch_url,
                impersonate="chrome",
                timeout=self.TIMEOUT_S,
                headers={"Referer": referer},
            )
            resp.raise_for_status()
        except RequestException:
            return None
        if not resp.headers.get("content-type", "").startswith("image/"):
            return None
        dest.write_bytes(resp.content)
        return dest
