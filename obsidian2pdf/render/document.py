"""Walk the document tree and emit one HTML document."""
from __future__ import annotations

import functools
import html as html_mod
import re
from pathlib import Path
from typing import Callable

import pygments
from markdown_it import MarkdownIt
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from ..collector.tree import NoteNode, SectionNode
from ..pagespec import PageSpec
from ..preprocess.pipeline import Pipeline
from ..preprocess.transforms import NoteContext

_THEME = Path(__file__).with_name("theme.css")


def _fence_renderer(highlight: bool) -> Callable[..., str]:
    """Every code block — fenced or indented, highlighted or not — renders
    as <pre class="codehilite"><code>, so one CSS rule covers them all."""

    def render_code(_renderer, tokens, idx, options, env) -> str:
        token = tokens[idx]
        lang = token.info.split()[0] if token.info.strip() else ""
        body = None
        if highlight and lang:
            try:
                lexer = get_lexer_by_name(lang)
            except ClassNotFound:
                pass  # unknown language: fall back to plain escaped text
            else:
                body = pygments.highlight(
                    token.content, lexer, HtmlFormatter(nowrap=True)
                )
        if body is None:
            body = html_mod.escape(token.content)
        return f'<pre class="codehilite"><code>{body}</code></pre>\n'

    return render_code


@functools.lru_cache(maxsize=None)
def _parser(highlight: bool) -> MarkdownIt:
    """CommonMark, matching what Obsidian itself parses: a list or a table
    may interrupt a paragraph, and list nesting follows relative indent
    (Obsidian indents by two spaces; classic Markdown demands four).

    breaks=True mirrors Obsidian's default with Strict line breaks off — a
    single newline is a line break. html=True lets the preprocess
    transforms emit the raw HTML spans they build for wikilinks and embeds.
    """
    md = MarkdownIt("commonmark", {"breaks": True, "html": True})
    md.enable(["table", "strikethrough"])
    # The preprocess transforms resolve local images to file:// URIs, a
    # scheme markdown-it rejects as unsafe by default — which would drop
    # every embedded image. This document is rendered offline into a
    # PDF/EPUB, not served, so the scheme is allowed back in.
    default_validate = md.validateLink

    def validate_link(url: str) -> bool:
        return url.strip().lower().startswith("file:") or default_validate(url)

    md.validateLink = validate_link
    rule = _fence_renderer(highlight)
    md.add_render_rule("fence", rule)
    md.add_render_rule("code_block", rule)
    return md


def _markdown_to_html(text: str, highlight: bool) -> str:
    return _parser(highlight).render(text)


def _demote(html: str, delta: int) -> str:
    """Shift h1..h6 down by delta levels, capped at h6."""
    if delta <= 0:
        return html
    return re.sub(
        r"<(/?)h([1-6])",
        lambda m: f"<{m.group(1)}h{min(6, int(m.group(2)) + delta)}",
        html,
    )


class DocumentRenderer:
    """Sections and notes render through the same recursion: a node at
    depth d gets an <h d> from its title, its body demoted d levels."""

    def __init__(
        self,
        pipeline: Pipeline,
        make_context: Callable[[Path], NoteContext],
        highlight: bool = True,
    ):
        self.pipeline = pipeline
        self.make_context = make_context
        self.highlight = highlight
        self.warnings: list[str] = []

    def render(self, node: SectionNode | NoteNode) -> str:
        return "".join(html for _, _, html in self.render_nodes(node))

    def render_nodes(
        self, node: SectionNode | NoteNode, depth: int = 1
    ) -> list[tuple[SectionNode | NoteNode, int, str]]:
        """Flat list of (node, depth, html_fragment) for every section and
        note in document order. Each fragment is that node's own heading
        plus its own body (a section's intro note, if any) — a section's
        children are separate entries, not nested inside its fragment."""
        return list(self._collect(node, depth))

    def _collect(self, node: SectionNode | NoteNode, depth: int):
        level = min(depth, 6)
        heading = f"<h{level}>{html_mod.escape(node.title)}</h{level}>\n"
        if isinstance(node, NoteNode):
            yield node, depth, heading + self._note_body(node, depth)
            return
        fragment = heading
        if node.intro is not None:
            fragment += self._note_body(node.intro, depth)
        yield node, depth, fragment
        for child in node.children:
            yield from self._collect(child, depth + 1)

    def _note_body(self, note: NoteNode, depth: int) -> str:
        ctx = self.make_context(note.path)
        text = note.path.read_text(encoding="utf-8")
        text = self.pipeline.run(text, ctx)
        self.warnings.extend(ctx.warnings)
        return _demote(_markdown_to_html(text, self.highlight), depth)


def stylesheet(page: PageSpec, highlight: bool = True) -> str:
    css = _THEME.read_text(encoding="utf-8")
    css = css.replace("__PAGE_SIZE__", page.css_size)
    css = css.replace("__BASE_FONT__", f"{page.base_font_pt}pt")
    if not highlight:
        return css
    pygments_css = HtmlFormatter(style="default").get_style_defs(".codehilite")
    return css + "\n" + pygments_css


def build_document(body_html: str, css: str, cover: str = "") -> str:
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{css}</style></head><body>{cover}{body_html}</body></html>"
    )
