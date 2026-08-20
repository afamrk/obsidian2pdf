"""Shared pytest fixtures: a synthetic Obsidian vault built into tmp_path."""
from __future__ import annotations

import base64
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pytest

# A valid 1x1 transparent PNG, used as a real embeddable test image.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY"
    "42YAAAAASUVORK5CYII="
)

ALPHA_MD = """---
Created: 2024-01-01
tags: test
---
## Alpha subheading

See ![[pic.png]] and [[Zeta|the other note]] and ![[Zeta#^block1]].

Ignored: ![[sound.mp3]]

```python
not_touched = "![[should-not-resolve.png]] [[should-not-link]]"
```

Inline `![[also-not-touched.png]]` stays literal.
"""

ZETA_MD = "Just a target note for wikilink/embed tests.\n"
CHILD_MD = "Child note content.\n"
PROJECT_MD = "Intro content for the Project folder.\n"


@dataclass
class Vault:
    root: Path
    project: Path


@pytest.fixture
def vault(tmp_path: Path) -> Vault:
    """A synthetic vault: Project/ with Alpha.md, Zeta.md, a folder note
    (Project.md), an attachments/pic.png, and a Sub/Child.md subfolder.

    context.mdb's row order is deliberately Zeta, Alpha, Sub — NOT
    alphabetical (Alpha, Sub, Zeta) — so --order makemd has something
    real to prove against the alpha default.
    """
    root = tmp_path / "vault"
    (root / ".obsidian").mkdir(parents=True)

    project = root / "Project"
    project.mkdir()
    (project / "Project.md").write_text(PROJECT_MD, encoding="utf-8")
    (project / "Alpha.md").write_text(ALPHA_MD, encoding="utf-8")
    (project / "Zeta.md").write_text(ZETA_MD, encoding="utf-8")

    attachments = project / "attachments"
    attachments.mkdir()
    (attachments / "pic.png").write_bytes(PNG_1X1)

    sub = project / "Sub"
    sub.mkdir()
    (sub / "Child.md").write_text(CHILD_MD, encoding="utf-8")

    space = project / ".space"
    space.mkdir()
    db = sqlite3.connect(space / "context.mdb")
    db.execute('CREATE TABLE files ("File" TEXT, "Created" TEXT)')
    for name in ("Project/Zeta.md", "Project/Alpha.md", "Project/Sub"):
        db.execute(
            'INSERT INTO files ("File", "Created") VALUES (?, ?)',
            (name, "2024-01-01"),
        )
    db.commit()
    db.close()

    return Vault(root=root, project=project)
