"""Tests for obsidian2pdf.vault."""
from __future__ import annotations

from obsidian2pdf.vault import build_attachment_index, find_vault_root


def test_find_vault_root_from_subfolder(vault):
    assert find_vault_root(vault.project / "Sub") == vault.root


def test_find_vault_root_from_file_path(vault):
    assert find_vault_root(vault.project / "Alpha.md") == vault.root


def test_find_vault_root_falls_back_without_marker(tmp_path):
    lone = tmp_path / "lone"
    lone.mkdir()
    assert find_vault_root(lone) == lone


def test_build_attachment_index_finds_image(vault):
    index = build_attachment_index(vault.root)
    assert index["pic.png"] == vault.project / "attachments" / "pic.png"


def test_build_attachment_index_skips_markdown_and_dot_directories(vault):
    index = build_attachment_index(vault.root)
    assert all(not name.endswith(".md") for name in index)
    assert "context.mdb" not in index  # lives inside .space, a dot-directory
