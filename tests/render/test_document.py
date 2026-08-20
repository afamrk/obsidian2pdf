"""Tests for obsidian2pdf.render.document."""
from __future__ import annotations

from obsidian2pdf.collector.ordering import MakeMdOrderStrategy
from obsidian2pdf.collector.tree import build_tree
from obsidian2pdf.pagespec import PRESETS
from obsidian2pdf.preprocess.pipeline import default_pipeline
from obsidian2pdf.preprocess.transforms import NoteContext
from obsidian2pdf.render.document import DocumentRenderer, stylesheet
from obsidian2pdf.vault import build_attachment_index


def _renderer(vault):
    idx = build_attachment_index(vault.root)
    return DocumentRenderer(
        default_pipeline(),
        lambda p: NoteContext(note_path=p, vault_root=vault.root, attachments=idx),
    )


def test_render_nodes_flat_structure_matches_tree(vault):
    tree = build_tree(vault.project, MakeMdOrderStrategy())
    renderer = _renderer(vault)
    nodes = renderer.render_nodes(tree)
    assert [(n.title, d) for n, d, _ in nodes] == [
        ("Project", 1),
        ("Zeta", 2),
        ("Alpha", 2),
        ("Sub", 2),
        ("Child", 3),
    ]


def test_render_equals_joined_render_nodes(vault):
    tree = build_tree(vault.project, MakeMdOrderStrategy())
    renderer = _renderer(vault)
    joined = "".join(html for _, _, html in renderer.render_nodes(tree))
    assert renderer.render(tree) == joined


def test_note_internal_headings_are_demoted(vault):
    # Alpha.md contains "## Alpha subheading" (markdown h2) and sits at
    # depth 2 in the tree -> demoted by 2 -> h4. Its own synthetic node
    # heading stays <h2>Alpha</h2>, generated separately at the correct
    # level (not itself demoted).
    tree = build_tree(vault.project, MakeMdOrderStrategy())
    renderer = _renderer(vault)
    alpha_fragment = next(
        html for node, _, html in renderer.render_nodes(tree) if node.title == "Alpha"
    )
    assert "<h4>Alpha subheading</h4>" in alpha_fragment
    assert "<h2>Alpha</h2>" in alpha_fragment


def test_stylesheet_includes_pygments_css_only_when_highlighting():
    with_highlight = stylesheet(PRESETS["a4"], highlight=True)
    without_highlight = stylesheet(PRESETS["a4"], highlight=False)
    assert ".codehilite" in with_highlight
    assert len(without_highlight) < len(with_highlight)


def test_stylesheet_injects_page_size_and_base_font():
    css = stylesheet(PRESETS["kobo-libra-colour"])
    assert "107.00mm 142.20mm" in css
    assert "8.5pt" in css
