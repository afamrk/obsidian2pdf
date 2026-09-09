"""Tests for obsidian2pdf.render.document."""
from __future__ import annotations

from obsidian2pdf.collector.ordering import MakeMdOrderStrategy
from obsidian2pdf.collector.tree import build_tree
from obsidian2pdf.pagespec import PRESETS
from obsidian2pdf.preprocess.pipeline import default_pipeline
from obsidian2pdf.preprocess.transforms import NoteContext
from obsidian2pdf.render.document import DocumentRenderer, stylesheet
from obsidian2pdf.vault import build_attachment_index


def _renderer(vault, highlight=True):
    idx = build_attachment_index(vault.root)
    return DocumentRenderer(
        default_pipeline(),
        lambda p: NoteContext(note_path=p, vault_root=vault.root, attachments=idx),
        highlight,
    )


def _render_markdown(vault, text: str, highlight=True) -> str:
    """Render one throwaway note, so a case reads as the markdown that goes
    in and the HTML that comes out."""
    note = vault.project / "Markdown.md"
    note.write_text(text, encoding="utf-8")
    tree = build_tree(note, MakeMdOrderStrategy())
    return _renderer(vault, highlight).render(tree)


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


# Obsidian parses CommonMark; classic Markdown differs in ways that quietly
# wrecked exported notes, so each case below pins one of those differences.


def test_list_interrupts_a_paragraph_without_a_blank_line(vault):
    html = _render_markdown(
        vault, "Clauses:\n- distinct rows\n- sorted rows\n"
    )
    assert "<ul>" in html
    assert "<li>distinct rows</li>" in html
    assert "- distinct rows" not in html  # not swallowed into the paragraph


def test_table_interrupts_a_paragraph_without_a_blank_line(vault):
    html = _render_markdown(vault, "Types:\n| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert "<table>" in html
    assert "<th>a</th>" in html


def test_two_space_indent_nests_the_sublist(vault):
    html = _render_markdown(vault, "- outer\n  - inner\n- second\n")
    assert html.count("<ul>") == 2
    assert "<ul>\n<li>inner</li>\n</ul>" in html


def test_single_newline_is_a_line_break(vault):
    # Obsidian's default (Strict line breaks off) breaks the line; classic
    # Markdown joins the two into one.
    html = _render_markdown(vault, "Line one\nLine two\n")
    assert "Line one<br />\nLine two" in html


def test_transform_html_survives_rendering(vault):
    html = _render_markdown(vault, "See [[Zeta|the other note]].\n")
    assert '<span class="wikilink">the other note</span>' in html


def test_resolved_image_uri_survives_rendering(vault):
    html = _render_markdown(vault, "![[pic.png]]\n")
    assert '<img src="file://' in html and "pic.png" in html


def test_code_block_is_highlighted_inside_one_codehilite_wrapper(vault):
    html = _render_markdown(vault, "```python\nx = 1\n```\n")
    assert html.count('<pre class="codehilite">') == 1
    assert "<span" in html.split('<pre class="codehilite">')[1]  # pygments


def test_code_block_without_highlighting_keeps_the_same_wrapper(vault):
    html = _render_markdown(vault, "```python\nx = 1\n```\n", highlight=False)
    assert '<pre class="codehilite"><code>x = 1\n</code></pre>' in html


def test_unknown_language_falls_back_to_escaped_text(vault):
    html = _render_markdown(vault, "```notalanguage\n<b>x</b>\n```\n")
    assert '<pre class="codehilite"><code>&lt;b&gt;x&lt;/b&gt;\n</code></pre>' in html
