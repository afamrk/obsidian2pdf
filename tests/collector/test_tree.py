"""Tests for obsidian2pdf.collector.tree."""
from __future__ import annotations

import pytest

from obsidian2pdf.collector.ordering import AlphabeticalOrderStrategy, MakeMdOrderStrategy
from obsidian2pdf.collector.tree import NoteNode, SectionNode, build_tree


def test_file_input_returns_note_node(vault):
    node = build_tree(vault.project / "Alpha.md", AlphabeticalOrderStrategy())
    assert isinstance(node, NoteNode)
    assert node.title == "Alpha"


def test_folder_input_returns_section_node(vault):
    node = build_tree(vault.project, MakeMdOrderStrategy())
    assert isinstance(node, SectionNode)
    assert node.title == "Project"


def test_folder_note_becomes_intro_and_excluded_from_children(vault):
    node = build_tree(vault.project, MakeMdOrderStrategy())
    assert node.intro is not None
    assert node.intro.title == "Project"
    assert "Project" not in [c.title for c in node.children]


def test_children_ordered_and_subfolder_recurses(vault):
    node = build_tree(vault.project, MakeMdOrderStrategy())
    assert [(c.title, type(c).__name__) for c in node.children] == [
        ("Zeta", "NoteNode"),
        ("Alpha", "NoteNode"),
        ("Sub", "SectionNode"),
    ]
    sub = node.children[2]
    assert [c.title for c in sub.children] == ["Child"]


def test_empty_folder_raises(tmp_path):
    empty = tmp_path / "Empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no markdown notes found"):
        build_tree(empty, AlphabeticalOrderStrategy())
