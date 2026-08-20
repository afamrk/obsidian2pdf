"""Document tree + rendered HTML fragments -> a .epub package via ebooklib.

Reuses the same DocumentRenderer used for PDF: render_nodes() gives one
(node, depth, html_fragment) entry per section/note, which this module
turns into one XHTML chapter each, nested via the book's TOC to mirror
the folder structure (the same way PDF bookmarks mirror it).

Each chapter's own internal headings (e.g. a note's "## Subheading") are
also indexed into nested TOC entries pointing at in-chapter anchors —
mirroring WeasyPrint's automatic per-heading PDF bookmarks, which the EPUB
path doesn't get "for free" the way the PDF path does.
"""
from __future__ import annotations

import html as html_mod
import re
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from ebooklib import epub

from ..collector.tree import NoteNode, SectionNode
from ..render.cover import cover_image
from ..render.document import DocumentRenderer

_IMG_SRC = re.compile(r'src="file://([^"]+)"')
_HEADING = re.compile(r"<h([1-6])(?:\s[^>]*)?>(.*?)</h\1>", re.DOTALL)
_TAG = re.compile(r"<[^>]+>")

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


class _ImageEmbedder:
    """Rewrites file:// image sources in a fragment into in-package paths,
    adding each source file to the book exactly once."""

    def __init__(self, book: epub.EpubBook):
        self.book = book
        self._items: dict[str, str] = {}
        self._counter = 0

    def embed(self, fragment: str) -> str:
        return _IMG_SRC.sub(self._replace, fragment)

    def _replace(self, match: re.Match) -> str:
        raw_path = urllib.parse.unquote(match.group(1))
        file_name = self._items.get(raw_path)
        if file_name is None:
            file_name = self._add_image(raw_path)
            self._items[raw_path] = file_name
        return f'src="{file_name}"'

    def _add_image(self, raw_path: str) -> str:
        self._counter += 1
        source = Path(raw_path)
        media_type = _MEDIA_TYPES.get(
            source.suffix.lower(), "application/octet-stream"
        )
        file_name = f"images/img{self._counter}{source.suffix}"
        item = epub.EpubImage(
            uid=f"img{self._counter}",
            file_name=file_name,
            media_type=media_type,
            content=source.read_bytes(),
        )
        self.book.add_item(item)
        return file_name


@dataclass
class _HeadingNode:
    text: str
    anchor: str
    children: list["_HeadingNode"] = field(default_factory=list)


def _index_headings(fragment: str, id_prefix: str) -> tuple[str, list[_HeadingNode]]:
    """Inject a unique id= into every heading in `fragment` and return the
    annotated HTML plus a nested tree of every heading *except* the first
    (the chapter's own synthetic title, already the chapter's own TOC
    entry — see write_epub's build())."""
    counter = 0
    flat: list[tuple[int, str, str]] = []

    def repl(match: re.Match) -> str:
        nonlocal counter
        counter += 1
        level = int(match.group(1))
        inner = match.group(2)
        anchor = f"{id_prefix}-h{counter}"
        text = html_mod.unescape(_TAG.sub("", inner)).strip()
        flat.append((level, text, anchor))
        return f'<h{level} id="{anchor}">{inner}</h{level}>'

    annotated = _HEADING.sub(repl, fragment)
    return annotated, _build_heading_tree(flat[1:])


def _build_heading_tree(flat: list[tuple[int, str, str]]) -> list[_HeadingNode]:
    root: list[_HeadingNode] = []
    stack: list[tuple[int, list[_HeadingNode]]] = [(0, root)]
    for level, text, anchor in flat:
        node = _HeadingNode(text=text, anchor=anchor)
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack[-1][1].append(node)
        stack.append((level, node.children))
    return root


def _heading_toc_entries(chapter_file_name: str, nodes: list[_HeadingNode]) -> tuple:
    entries = []
    for node in nodes:
        link = epub.Link(f"{chapter_file_name}#{node.anchor}", node.text, node.anchor)
        if node.children:
            entries.append((link, _heading_toc_entries(chapter_file_name, node.children)))
        else:
            entries.append(link)
    return tuple(entries)


def _make_chapter(
    uid: str, title: str, content: str, style: epub.EpubItem
) -> epub.EpubHtml:
    chapter = epub.EpubHtml(uid=uid, title=title, file_name=f"{uid}.xhtml", lang="en")
    chapter.content = (
        "<html><head>"
        f'<link rel="stylesheet" href="{style.file_name}" />'
        f"</head><body>{content}</body></html>"
    )
    chapter.add_item(style)
    return chapter


def write_epub(
    tree: SectionNode | NoteNode,
    renderer: DocumentRenderer,
    out_path: Path,
    css: str,
    cover: str = "",
    custom_cover_image: tuple[bytes, str] | None = None,
) -> None:
    fragments = {id(node): html for node, _, html in renderer.render_nodes(tree)}

    book = epub.EpubBook()
    book.set_identifier(out_path.stem)
    book.set_title(tree.title)
    book.set_language("en")

    style = epub.EpubItem(
        uid="style", file_name="style.css", media_type="text/css",
        content=css.encode("utf-8"),
    )
    book.add_item(style)
    embedder = _ImageEmbedder(book)

    spine: list = ["nav"]
    toc: list = []

    if cover:
        cover_chapter = _make_chapter("cover", "Cover", embedder.embed(cover), style)
        book.add_item(cover_chapter)
        spine.append(cover_chapter)
        toc.append(cover_chapter)
        # The Cover *page* above is only ever seen inside the reading flow.
        # Library/shelf views (e.g. Kobo's home screen) show a thumbnail
        # from the EPUB's registered cover-image instead, which is a
        # separate mechanism (OPF manifest properties="cover-image" +
        # legacy <meta name="cover">) that create_page=False skips
        # duplicating as a second cover page (EpubCoverHtml defaults to
        # the same uid/file_name as our own chapter above). media_type is
        # left for ebooklib to auto-detect from the file extension.
        if custom_cover_image is not None:
            image_bytes, image_file_name = custom_cover_image
        else:
            image_bytes, image_file_name = cover_image(tree.title), "cover-image.png"
        book.set_cover(image_file_name, image_bytes, create_page=False)

    counter = [0]

    def build(node: SectionNode | NoteNode):
        counter[0] += 1
        uid = f"c{counter[0]}"
        raw_content = embedder.embed(fragments[id(node)])
        content, heading_tree = _index_headings(raw_content, uid)
        chapter = _make_chapter(uid, node.title, content, style)
        book.add_item(chapter)
        spine.append(chapter)

        heading_entries = _heading_toc_entries(chapter.file_name, heading_tree)
        if isinstance(node, SectionNode) and node.children:
            children_toc = tuple(build(child) for child in node.children)
            combined = heading_entries + children_toc
            return (epub.Link(chapter.file_name, chapter.title, chapter.id), combined)
        if heading_entries:
            return (epub.Link(chapter.file_name, chapter.title, chapter.id), heading_entries)
        return chapter

    toc.append(build(tree))
    book.toc = tuple(toc)
    book.spine = spine
    book.add_item(epub.EpubNcx())
    # Without an explicit title, ebooklib's nav.xhtml <h2> falls back to the
    # book title, which duplicates the first chapter when a folder export's
    # root chapter shares the book's name (e.g. "Kubernetes" right above
    # "Kubernetes" in a reader's outline).
    book.add_item(epub.EpubNav(title="Contents"))

    epub.write_epub(str(out_path), book)
