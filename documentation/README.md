# obsidian2pdf documentation

Production documentation for obsidian2pdf — a CLI that exports an Obsidian
note or folder to a single PDF or EPUB, with a page preset matching the
Kobo Libra Colour screen.

For install/usage quick-start, see the [project README](../README.md).
This folder covers the *why* and *how it fits together*.

## Contents

- **[architecture.md](architecture.md)** — the four-stage pipeline, data
  flow from vault to output file, and the design patterns used (Composite,
  Strategy, Pipeline of Transforms, Registry, Adapter).
- **[file-structure.md](file-structure.md)** — every source file, its
  single responsibility, and its dependencies on other modules.
- **[design-decisions.md](design-decisions.md)** — the significant choices
  made along the way and why, including two real bugs found in production
  and how they shaped the code (Imgur's fake-200 responses, EPUB's
  duplicate TOC header).
- **[cli-reference.md](cli-reference.md)** — every flag, its default, and
  what it does for each output format.
- **[testing.md](testing.md)** — how the test suite is structured, the
  synthetic vault fixture, and how to extend it.

## Project facts

- **Language:** Python ≥3.10
- **Core dependencies:** `markdown`, `weasyprint`, `pygments`, `curl_cffi`,
  `ebooklib`, `Pillow`
- **Test dependencies:** `pytest`, `pypdf` (install via `pip install -e ".[test]"`)
- **Entry point:** `obsidian2pdf` console script → `obsidian2pdf.cli:main`
- **No automated tests were part of the original v1 scope** — they were
  added in a follow-up pass; see [testing.md](testing.md).
