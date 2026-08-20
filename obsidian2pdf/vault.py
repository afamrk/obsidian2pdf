"""Vault root discovery and attachment lookup."""
from __future__ import annotations

from pathlib import Path

IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "bmp", "avif"}


def find_vault_root(start: Path) -> Path:
    """Walk up from `start` until a directory containing .obsidian is found.

    Falls back to `start` (or its parent for files) when no vault marker
    exists, so exports outside a vault still resolve relative embeds.
    """
    cur = start if start.is_dir() else start.parent
    for candidate in (cur, *cur.parents):
        if (candidate / ".obsidian").is_dir():
            return candidate
    return cur


def build_attachment_index(vault_root: Path) -> dict[str, Path]:
    """Map bare file name -> absolute path for every non-markdown file.

    Obsidian resolves `![[img.png]]` vault-wide by name; this index mirrors
    that. Sorted walk makes the pick deterministic when names collide.
    """
    index: dict[str, Path] = {}
    for p in sorted(vault_root.rglob("*")):
        if not p.is_file() or p.suffix == ".md":
            continue
        if any(part.startswith(".") for part in p.relative_to(vault_root).parts):
            continue
        index.setdefault(p.name, p)
    return index
