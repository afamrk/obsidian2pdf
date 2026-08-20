"""Tests for obsidian2pdf.preprocess.pipeline."""
from __future__ import annotations

from obsidian2pdf.preprocess.pipeline import default_pipeline
from obsidian2pdf.preprocess.transforms import NoteContext


def test_fenced_code_block_untouched(vault):
    text = (
        "Before\n\n"
        '```python\n'
        'x = "![[embed.png]] [[link]]"\n'
        '```\n\n'
        "After [[Real Link]]\n"
    )
    ctx = NoteContext(note_path=vault.project / "Alpha.md", vault_root=vault.root, attachments={})
    out = default_pipeline().run(text, ctx)
    assert '```python\nx = "![[embed.png]] [[link]]"\n```' in out
    assert '<span class="wikilink">Real Link</span>' in out


def test_inline_code_untouched(vault):
    text = "Inline `![[y.png]]` stays.\n"
    ctx = NoteContext(note_path=vault.project / "Alpha.md", vault_root=vault.root, attachments={})
    out = default_pipeline().run(text, ctx)
    assert "`![[y.png]]`" in out


def test_full_alpha_note_pipeline_output(vault):
    from obsidian2pdf.vault import build_attachment_index

    idx = build_attachment_index(vault.root)
    text = (vault.project / "Alpha.md").read_text(encoding="utf-8")
    ctx = NoteContext(
        note_path=vault.project / "Alpha.md",
        vault_root=vault.root,
        attachments=idx,
        ignored_exts=frozenset({"mp3"}),
    )
    out = default_pipeline().run(text, ctx)
    assert "Created: 2024-01-01" not in out  # frontmatter stripped
    assert "pic.png" in out and "file://" in out  # image resolved
    assert '<span class="wikilink">the other note</span>' in out
    assert '<span class="embed-ref">&#128196; Zeta</span>' in out
    assert "sound.mp3" not in out  # ignored extension dropped
    assert 'not_touched = "![[should-not-resolve.png]] [[should-not-link]]"' in out
    assert ctx.warnings == []
