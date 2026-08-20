"""Tests for obsidian2pdf.writer.pdf."""
from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from obsidian2pdf.collector.ordering import MakeMdOrderStrategy
from obsidian2pdf.collector.tree import build_tree
from obsidian2pdf.pagespec import resolve_size
from obsidian2pdf.preprocess.pipeline import default_pipeline
from obsidian2pdf.preprocess.transforms import NoteContext
from obsidian2pdf.render.cover import cover_html
from obsidian2pdf.render.document import DocumentRenderer, build_document, stylesheet
from obsidian2pdf.vault import build_attachment_index
from obsidian2pdf.writer.pdf import write_pdf


def test_write_pdf_page_geometry_matches_pagespec(vault, tmp_path):
    idx = build_attachment_index(vault.root)
    tree = build_tree(vault.project, MakeMdOrderStrategy())
    renderer = DocumentRenderer(
        default_pipeline(),
        lambda p: NoteContext(note_path=p, vault_root=vault.root, attachments=idx),
    )
    body = renderer.render(tree)
    page = resolve_size("kobo-libra-colour")
    document = build_document(body, stylesheet(page), cover_html(tree.title))

    out = tmp_path / "out.pdf"
    write_pdf(document, out)

    reader = PdfReader(str(out))
    box = reader.pages[0].mediabox
    assert round(float(box.width)) == 303
    assert round(float(box.height)) == 403
    assert len(reader.pages) > 1
    assert len(reader.outline) > 0
