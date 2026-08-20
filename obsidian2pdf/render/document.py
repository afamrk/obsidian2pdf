"""Walk the document tree and emit one HTML document."""
from __future__ import annotations

import html as html_mod
import re
from pathlib import Path
from typing import Callable

import markdown
from pygments.formatters import HtmlFormatter

from ..collector.tree import NoteNode, SectionNode
from ..pagespec import PageSpec
from ..preprocess.pipeline import Pipeline
from ..preprocess.transforms import NoteContext

_MD_EXTENSIONS = ["fenced_code", "codehilite", "tables", "sane_lists"]
_THEME = Path(__file__).with_name("theme.css")


def _markdown_to_html(text: str, highlight: bool) -> str:
    configs = {"codehilite": {"guess_lang": False, "use_pygments": highlight}}
    return markdown.markdown(
        text, extensions=_MD_EXTENSIONS, extension_configs=configs
    )


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
