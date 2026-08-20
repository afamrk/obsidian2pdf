"""Document tree: Composite of folder sections and notes."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .ordering import OrderingStrategy


@dataclass
class NoteNode:
    path: Path
    title: str


@dataclass
class SectionNode:
    path: Path
    title: str
    intro: NoteNode | None = None  # the folder note (X/X.md), if any
    children: list["SectionNode | NoteNode"] = field(default_factory=list)


def build_tree(input_path: Path, strategy: OrderingStrategy) -> SectionNode | NoteNode:
    input_path = input_path.resolve()
    if input_path.is_file():
        return NoteNode(input_path, input_path.stem)
    section = _build_section(input_path, strategy)
    if section.intro is None and not section.children:
        raise ValueError(f"no markdown notes found under {input_path}")
    return section


def _has_notes(folder: Path) -> bool:
    return any(
        not any(part.startswith(".") for part in p.relative_to(folder).parts)
        for p in folder.rglob("*.md")
    )


def _build_section(folder: Path, strategy: OrderingStrategy) -> SectionNode:
    section = SectionNode(folder, folder.name)
    entries: list[Path] = []
    for child in folder.iterdir():
        if child.name.startswith("."):
            continue
        if child.is_file() and child.suffix == ".md":
            if child.stem == folder.name:
                section.intro = NoteNode(child, child.stem)
            else:
                entries.append(child)
        elif child.is_dir() and _has_notes(child):
            entries.append(child)
    for path in strategy.order(folder, entries):
        if path.is_dir():
            section.children.append(_build_section(path, strategy))
        else:
            section.children.append(NoteNode(path, path.stem))
    return section
