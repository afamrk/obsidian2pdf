"""Tests for obsidian2pdf.collector.ordering."""
from __future__ import annotations

from pathlib import Path

from obsidian2pdf.collector.ordering import (
    AlphabeticalOrderStrategy,
    MakeMdOrderStrategy,
)


def _touch(*paths: Path) -> list[Path]:
    for p in paths:
        p.touch()
    return list(paths)


def test_alphabetical_natural_sort(tmp_path):
    entries = _touch(
        tmp_path / "10 foo.md", tmp_path / "2 foo.md", tmp_path / "1 foo.md"
    )
    ordered = AlphabeticalOrderStrategy().order(tmp_path, entries)
    assert [p.name for p in ordered] == ["1 foo.md", "2 foo.md", "10 foo.md"]


def test_makemd_orders_by_context_mdb_row_order(vault):
    entries = [
        vault.project / "Alpha.md",
        vault.project / "Zeta.md",
        vault.project / "Sub",
    ]
    ordered = MakeMdOrderStrategy().order(vault.project, entries)
    assert [p.name for p in ordered] == ["Zeta.md", "Alpha.md", "Sub"]


def test_makemd_appends_unranked_entries_alphabetically(vault):
    extra = vault.project / "Omega.md"
    extra.touch()
    entries = [
        vault.project / "Alpha.md",
        vault.project / "Zeta.md",
        vault.project / "Sub",
        extra,
    ]
    ordered = MakeMdOrderStrategy().order(vault.project, entries)
    assert [p.name for p in ordered] == ["Zeta.md", "Alpha.md", "Sub", "Omega.md"]


def test_makemd_skips_table_rows_missing_on_disk(vault):
    # context.mdb references Zeta.md and Sub too, but only Alpha.md is
    # passed in as an actual entry -> the other rows are simply ignored.
    ordered = MakeMdOrderStrategy().order(vault.project, [vault.project / "Alpha.md"])
    assert [p.name for p in ordered] == ["Alpha.md"]


def test_makemd_falls_back_to_alphabetical_without_database(tmp_path):
    entries = _touch(tmp_path / "b.md", tmp_path / "a.md")
    ordered = MakeMdOrderStrategy().order(tmp_path, entries)
    assert [p.name for p in ordered] == ["a.md", "b.md"]


def test_makemd_falls_back_when_database_unreadable(tmp_path):
    (tmp_path / ".space").mkdir()
    (tmp_path / ".space" / "context.mdb").write_text("not a sqlite file")
    entries = _touch(tmp_path / "b.md", tmp_path / "a.md")
    ordered = MakeMdOrderStrategy().order(tmp_path, entries)
    assert [p.name for p in ordered] == ["a.md", "b.md"]
