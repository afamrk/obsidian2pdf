"""Tests for obsidian2pdf.preprocess.transforms."""
from __future__ import annotations

from pathlib import Path

from curl_cffi.requests.exceptions import RequestException

from obsidian2pdf.preprocess import transforms as T
from obsidian2pdf.preprocess.transforms import (
    FrontmatterStripper,
    IgnoredMediaFilter,
    ImageEmbedResolver,
    LocalMdImageResolver,
    NoteContext,
    NoteEmbedToLink,
    RemoteImageFetcher,
    VideoEmbedToLink,
    WikilinkToText,
)


class FakeResponse:
    def __init__(self, status_code=200, headers=None, content=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RequestException(f"HTTP {self.status_code}")


def _ctx(vault, **kwargs) -> NoteContext:
    kwargs.setdefault("attachments", {})
    return NoteContext(
        note_path=vault.project / "Alpha.md",
        vault_root=vault.root,
        **kwargs,
    )


def test_frontmatter_stripper_removes_leading_block(vault):
    text = "---\nCreated: 2024-01-01\n---\nBody text\n"
    assert FrontmatterStripper().apply(text, _ctx(vault)) == "Body text\n"


def test_frontmatter_stripper_leaves_text_without_frontmatter(vault):
    text = "No frontmatter here\n"
    assert FrontmatterStripper().apply(text, _ctx(vault)) == text


def test_ignored_media_filter_drops_matching_extensions(vault):
    ctx = _ctx(vault, ignored_exts=frozenset({"mp3"}))
    text = "See ![[sound.mp3]] and ![](http://x.com/a.mp3) and ![[keep.png]]"
    out = IgnoredMediaFilter().apply(text, ctx)
    assert "sound.mp3" not in out
    assert "a.mp3" not in out
    assert "keep.png" in out


def test_video_embed_to_link_only_rewrites_video_hosts(vault):
    ctx = _ctx(vault)
    yt = VideoEmbedToLink().apply("![](https://www.youtube.com/watch?v=abc)", ctx)
    assert '<a class="video-link"' in yt
    other = VideoEmbedToLink().apply("![alt](https://example.com/pic.png)", ctx)
    assert other == "![alt](https://example.com/pic.png)"


def test_image_embed_resolver_finds_sibling_attachment(vault):
    ctx = _ctx(vault, attachments={"pic.png": vault.project / "attachments" / "pic.png"})
    out = ImageEmbedResolver().apply("![[pic.png]]", ctx)
    assert out == f"![]({(vault.project / 'attachments' / 'pic.png').as_uri()})"


def test_image_embed_resolver_warns_and_placeholders_on_miss(vault):
    ctx = _ctx(vault)
    out = ImageEmbedResolver().apply("![[missing.png]]", ctx)
    assert "missing-embed" in out
    assert ctx.warnings == ["Alpha.md: missing image 'missing.png'"]


def test_note_embed_to_link_produces_styled_reference(vault):
    out = NoteEmbedToLink().apply("![[Zeta#^block1]]", _ctx(vault))
    assert out == '<span class="embed-ref">&#128196; Zeta</span>'


def test_wikilink_to_text_uses_alias_when_present(vault):
    out = WikilinkToText().apply("[[Zeta|the other note]]", _ctx(vault))
    assert out == '<span class="wikilink">the other note</span>'


def test_wikilink_to_text_uses_target_without_alias(vault):
    out = WikilinkToText().apply("[[Zeta]]", _ctx(vault))
    assert out == '<span class="wikilink">Zeta</span>'


def test_wikilink_to_text_uses_heading_for_same_note_link(vault):
    out = WikilinkToText().apply("[[#Exported vs Unexported Fields]]", _ctx(vault))
    assert out == '<span class="wikilink">Exported vs Unexported Fields</span>'


def test_wikilink_to_text_joins_target_and_section(vault):
    out = WikilinkToText().apply("[[Zeta#Structs]]", _ctx(vault))
    assert out == '<span class="wikilink">Zeta &gt; Structs</span>'


def test_wikilink_to_text_keeps_block_reference(vault):
    out = WikilinkToText().apply("[[Zeta#^abc123]]", _ctx(vault))
    assert out == '<span class="wikilink">Zeta &gt; ^abc123</span>'


def test_wikilink_to_text_alias_wins_over_section(vault):
    out = WikilinkToText().apply("[[Zeta#Structs|the other note]]", _ctx(vault))
    assert out == '<span class="wikilink">the other note</span>'


def test_local_md_image_resolver_resolves_relative_path(vault):
    ctx = _ctx(vault)
    out = LocalMdImageResolver().apply("![alt](attachments/pic.png)", ctx)
    assert out == f"![alt]({(vault.project / 'attachments' / 'pic.png').as_uri()})"


def test_remote_image_fetcher_success(vault, tmp_path, monkeypatch):
    monkeypatch.setattr(
        T.curl_requests, "get",
        lambda url, **kw: FakeResponse(200, {"content-type": "image/png"}, b"PNGDATA"),
    )
    ctx = _ctx(vault, image_cache_dir=tmp_path)
    out = RemoteImageFetcher().apply("![alt](https://example.com/img.png)", ctx)
    assert out.startswith("![alt](file://")
    assert ctx.warnings == []


def test_remote_image_fetcher_non_200_becomes_link_with_warning(vault, tmp_path, monkeypatch):
    monkeypatch.setattr(T.curl_requests, "get", lambda url, **kw: FakeResponse(429))
    ctx = _ctx(vault, image_cache_dir=tmp_path)
    out = RemoteImageFetcher().apply("![alt](https://example.com/img2.png)", ctx)
    assert out == '<a href="https://example.com/img2.png">https://example.com/img2.png</a>'
    assert ctx.warnings == ["Alpha.md: could not fetch https://example.com/img2.png"]


def test_remote_image_fetcher_imgur_html_200_regression(vault, tmp_path, monkeypatch):
    """Regression test: i.imgur.com can return HTTP 200 with an HTML body
    for a dead link. That must be treated as a failure, not cached as an
    image — this is the exact bug fixed earlier in the project."""
    monkeypatch.setattr(
        T.curl_requests, "get",
        lambda url, **kw: FakeResponse(200, {"content-type": "text/html"}, b"<html></html>"),
    )
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    ctx = _ctx(vault, image_cache_dir=cache_dir)
    out = RemoteImageFetcher().apply("![alt](https://i.imgur.com/abc123.png)", ctx)
    assert out == '<a href="https://i.imgur.com/abc123.png">https://i.imgur.com/abc123.png</a>'
    assert ctx.warnings == ["Alpha.md: could not fetch https://i.imgur.com/abc123.png"]
    assert list(cache_dir.iterdir()) == []
