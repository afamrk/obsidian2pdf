"""Ordering strategies for a folder's children (Strategy pattern)."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Protocol


class OrderingStrategy(Protocol):
    def order(self, folder: Path, entries: list[Path]) -> list[Path]: ...


def _natural_key(path: Path) -> list:
    return [
        int(tok) if tok.isdigit() else tok.casefold()
        for tok in re.split(r"(\d+)", path.name)
    ]


class AlphabeticalOrderStrategy:
    """Natural sort: '2 foo' comes before '10 foo'."""

    def order(self, folder: Path, entries: list[Path]) -> list[Path]:
        return sorted(entries, key=_natural_key)


class MakeMdOrderStrategy:
    """Manual order from make.md: row order of the `files` table in
    <folder>/.space/context.mdb (verified: rowid order == sidebar order).

    Entries missing from the table are appended alphabetically; table rows
    with no file on disk are ignored. No database -> alphabetical.
    """

    def order(self, folder: Path, entries: list[Path]) -> list[Path]:
        rank = {name: i for i, name in enumerate(self._read_order(folder))}
        ranked = sorted(
            (e for e in entries if e.name in rank), key=lambda e: rank[e.name]
        )
        unranked = [e for e in entries if e.name not in rank]
        return ranked + AlphabeticalOrderStrategy().order(folder, unranked)

    @staticmethod
    def _read_order(folder: Path) -> list[str]:
        db = folder / ".space" / "context.mdb"
        if not db.is_file():
            return []
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                rows = con.execute(
                    'SELECT "File" FROM files ORDER BY rowid'
                ).fetchall()
            finally:
                con.close()
        except sqlite3.Error:
            return []
        # Values are vault-relative paths ("Kubernetes/Basic.md"); keep names.
        return [Path(str(r[0])).name for r in rows]
