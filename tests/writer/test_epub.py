"""Tests for obsidian2pdf.writer.epub."""
from __future__ import annotations

import zipfile
from pathlib import Path

from obsidian2pdf.collector.ordering import MakeMdOrderStrategy
from obsidian2pdf.collector.tree import build_tree
from obsidian2pdf.pagespec import PRESETS
from obsidian2pdf.preprocess.pipeline import default_pipeline
from obsidian2pdf.preprocess.transforms import NoteContext
from obsidian2pdf.render.cover import cover_html
from obsidian2pdf.render.document import DocumentRenderer, stylesheet
from obsidian2pdf.vault import build_attachment_index
from obsidian2pdf.writer.epub import write_epub


def _renderer(vault):
    idx = build_attachment_index(vault.root)
    return DocumentRenderer(
        default_pipeline(),
        lambda p: NoteContext(note_path=p, vault_root=vault.root, attachments=idx),
    )


def test_nav_heading_is_not_duplicated_book_title(vault, tmp_path):
    """Regression test for the 'Kubernetes' shown twice in a reader's
    outline bug: nav.xhtml's own <h2> must not equal the book title when
    the root chapter is also titled after the book."""
    tree = build_tree(vault.project, MakeMdOrderStrategy())
    renderer = _renderer(vault)
    css = stylesheet(PRESETS["a4"])
    out = tmp_path / "out.epub"
    write_epub(tree, renderer, out, css, cover_html(tree.title))

    with zipfile.ZipFile(out) as z:
        nav = z.read("EPUB/nav.xhtml").decode("utf-8")
    assert "<h2>Contents</h2>" in nav
    assert "<h2>Project</h2>" not in nav


def test_nav_order_matches_tree_order(vault, tmp_path):
    tree = build_tree(vault.project, MakeMdOrderStrategy())
    renderer = _renderer(vault)
    css = stylesheet(PRESETS["a4"])
    out = tmp_path / "out.epub"
    write_epub(tree, renderer, out, css, cover_html(tree.title))

    with zipfile.ZipFile(out) as z:
        nav = z.read("EPUB/nav.xhtml").decode("utf-8")
    positions = [nav.index(f">{label}<") for label in ("Zeta", "Alpha", "Sub", "Child")]
    assert positions == sorted(positions)
    assert nav.index("Cover</a>") < positions[0]


def test_embedded_images_are_real_bytes_not_html(vault, tmp_path):
    tree = build_tree(vault.project, MakeMdOrderStrategy())
    renderer = _renderer(vault)
    css = stylesheet(PRESETS["a4"])
    out = tmp_path / "out.epub"
    write_epub(tree, renderer, out, css, cover_html(tree.title))

    with zipfile.ZipFile(out) as z:
        image_names = [n for n in z.namelist() if n.startswith("EPUB/images/")]
        assert image_names
        image_bytes = z.read(image_names[0])
    assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_no_cover_produces_no_cover_entry(vault, tmp_path):
    tree = build_tree(vault.project, MakeMdOrderStrategy())
    renderer = _renderer(vault)
    css = stylesheet(PRESETS["a4"])
    out = tmp_path / "out.epub"
    write_epub(tree, renderer, out, css, cover="")

    with zipfile.ZipFile(out) as z:
        nav = z.read("EPUB/nav.xhtml").decode("utf-8")
    assert "Cover</a>" not in nav


def test_cover_image_is_registered_for_library_thumbnails(vault, tmp_path):
    """Regression test for 'no cover for the epub': a Cover *page* alone
    isn't picked up by library/shelf views (e.g. Kobo's home screen) —
    those read the EPUB's registered cover-image (OPF manifest
    properties="cover-image" + legacy <meta name="cover">), which must
    point at a real embedded image, not just be absent."""
    tree = build_tree(vault.project, MakeMdOrderStrategy())
    renderer = _renderer(vault)
    css = stylesheet(PRESETS["a4"])
    out = tmp_path / "out.epub"
    write_epub(tree, renderer, out, css, cover_html(tree.title))

    with zipfile.ZipFile(out) as z:
        opf = z.read("EPUB/content.opf").decode("utf-8")
        cover_item = next(
            line for line in opf.splitlines() if 'properties="cover-image"' in line
        )
        href = cover_item.split('href="')[1].split('"')[0]
        image_bytes = z.read(f"EPUB/{href}")

    assert 'name="cover"' in opf
    assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    # Registering the cover image must not create a second reading-flow
    # cover page alongside our own styled one.
    assert opf.count('id="cover"') == 1


def test_no_cover_skips_cover_image_too(vault, tmp_path):
    tree = build_tree(vault.project, MakeMdOrderStrategy())
    renderer = _renderer(vault)
    css = stylesheet(PRESETS["a4"])
    out = tmp_path / "out.epub"
    write_epub(tree, renderer, out, css, cover="")

    with zipfile.ZipFile(out) as z:
        opf = z.read("EPUB/content.opf").decode("utf-8")
    assert "cover-image" not in opf


def test_internal_headings_get_nested_toc_entries(vault, tmp_path):
    """Regression test for 'only file heading are present': a note's own
    internal headings (e.g. Alpha.md's '## Alpha subheading') must appear
    as nested nav entries pointing at in-chapter anchors, not just the
    note's own top-level chapter entry — mirroring the PDF path, where
    WeasyPrint generates a bookmark for every heading automatically."""
    tree = build_tree(vault.project, MakeMdOrderStrategy())
    renderer = _renderer(vault)
    css = stylesheet(PRESETS["a4"])
    out = tmp_path / "out.epub"
    write_epub(tree, renderer, out, css, cover_html(tree.title))

    with zipfile.ZipFile(out) as z:
        nav = z.read("EPUB/nav.xhtml").decode("utf-8")
        alpha_chapter = next(
            n for n in z.namelist() if n.startswith("EPUB/c") and n.endswith(".xhtml")
            and b"Alpha subheading" in z.read(n)
        )
        chapter_content = z.read(alpha_chapter).decode("utf-8")

    assert '>Alpha subheading</a>' in nav
    heading_href = next(
        line for line in nav.splitlines() if "Alpha subheading</a>" in line
    )
    anchor = heading_href.split('href="')[1].split('"')[0]
    assert anchor.startswith(alpha_chapter.split("/")[-1] + "#")
    anchor_id = anchor.split("#", 1)[1]
    assert f'id="{anchor_id}"' in chapter_content


def test_custom_cover_image_used_instead_of_generated(vault, tmp_path):
    tree = build_tree(vault.project, MakeMdOrderStrategy())
    renderer = _renderer(vault)
    css = stylesheet(PRESETS["a4"])
    out = tmp_path / "out.epub"
    custom_bytes = b"not-a-real-png-but-a-marker-value"
    write_epub(
        tree, renderer, out, css, cover_html(tree.title),
        custom_cover_image=(custom_bytes, "cover-image.jpg"),
    )

    with zipfile.ZipFile(out) as z:
        opf = z.read("EPUB/content.opf").decode("utf-8")
        cover_item = next(
            line for line in opf.splitlines() if 'properties="cover-image"' in line
        )
        href = cover_item.split('href="')[1].split('"')[0]
        image_bytes = z.read(f"EPUB/{href}")

    assert href == "cover-image.jpg"
    assert 'media-type="image/jpeg"' in cover_item
    assert image_bytes == custom_bytes
