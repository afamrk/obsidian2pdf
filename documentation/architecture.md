# Architecture

## Overview

obsidian2pdf turns a note or a folder of notes into one output file (PDF or
EPUB) through four independent stages. Each stage has one job, consumes the
previous stage's output, and knows nothing about the stages after it:

```
 input path            DocumentTree           HTML fragments         output file
┌──────────┐  collect  ┌───────────┐  render  ┌──────────────┐ write ┌─────────┐
│  vault /  │ ────────► │ Section/  │ ───────► │  per-node    │ ────► │ .pdf /  │
│  folder / │           │ NoteNode  │          │  HTML, one   │       │ .epub   │
│  note     │           │  tree     │          │  per section │       │         │
└──────────┘           └───────────┘          │  and note    │       └─────────┘
                              ▲                └──────────────┘
                              │                       ▲
                        ordering strategy      preprocessing pipeline
                        (alpha / make.md)       (per-note transforms)
```

The same `DocumentTree` and the same rendered HTML fragments feed *both*
writers (PDF and EPUB) — only the last step (packaging) differs. This is
why adding EPUB support later required exactly one new module
(`writer/epub.py`) and one small addition to the renderer
(`render_nodes()`), not a parallel pipeline.

## The four stages

### 1. Collect (`collector/`)

Walks the input path and builds a `DocumentTree`: a `SectionNode` (folder)
or `NoteNode` (file), recursively. A folder's own note (`X/X.md`) becomes
that section's `intro`, not a child — it renders as the section's opening
content instead of a separate entry.

Ordering of a folder's children is delegated to an `OrderingStrategy`
(Strategy pattern, see [design-decisions.md](design-decisions.md)):
natural alphabetical sort by default, or the make.md plugin's manual
drag-order when `--order makemd` is passed.

### 2. Preprocess (`preprocess/`)

Each note's raw Markdown text runs through a `Pipeline` of `Transform`
objects, in a fixed order, with fenced code blocks and inline code spans
masked out first so Obsidian syntax inside code samples is never rewritten.
Each transform does exactly one job — strip frontmatter, resolve
`![[image]]` embeds, drop ignored media types, fetch remote images, etc.
See [file-structure.md](file-structure.md) for the full list and order.

Network-touching code (`RemoteImageFetcher`) delegates host-specific fetch
quirks to `host_adapters.py` (Adapter pattern) so hosts with unusual
hotlink protection (currently Imgur) don't clutter the fetcher itself.

### 3. Render (`render/`)

`DocumentRenderer.render_nodes()` walks the `DocumentTree` and returns a
flat list of `(node, depth, html_fragment)` — one entry per section and
note, in document order. Each fragment is that node's own heading (from its
title) plus its own body; a section's children are *separate* entries, not
nested inside the section's own fragment. This flat-with-depth
representation is deliberately reusable:

- The PDF writer just joins every fragment into one string:
  `render()` is a one-line wrapper around `render_nodes()`.
- The EPUB writer turns each entry into its own XHTML chapter, nesting
  chapters by depth to build the EPUB's table of contents.

Heading levels are demoted per node depth (a note's own `# Foo` becomes
`<h{depth+1}>`, capped at `<h6>`), so a deeply nested subfolder's notes
still produce valid, sequential heading levels.

### 4. Write (`writer/`)

- `writer/pdf.py` — the joined HTML + a CSS stylesheet (with `@page` sized
  from a `PageSpec`) goes straight into WeasyPrint's `HTML(...).write_pdf()`.
- `writer/epub.py` — walks `render_nodes()`'s flat output, builds one
  `ebooklib.epub.EpubHtml` chapter per node, embeds every referenced local
  image as a real binary item in the package (not a `file://` link — EPUB
  is a zip archive, not a live filesystem), and nests chapters into
  `book.toc` to mirror the folder structure.

## Supporting modules

- **`pagespec.py`** — a `Registry`-style lookup: named presets
  (`a4`, `kobo-libra-colour`, ...) or a parsed custom size (`WxH@DPI`,
  `WxHmm`) resolve to a `PageSpec(width_mm, height_mm, base_font_pt)`.
  `--size` only affects PDF; EPUB is reflowable and has no fixed page.
- **`vault.py`** — finds the vault root (nearest ancestor containing
  `.obsidian`) and builds a vault-wide `{filename: path}` index so
  `![[img.png]]` can resolve the way Obsidian itself resolves it: by bare
  name, vault-wide, not just relative to the current note.
- **`cli.py`** — the only module that knows about all the others. Parses
  arguments, wires collector → pipeline → renderer → the chosen writer, and
  is the sole place error handling turns into a process exit code.

## Data flow example

Exporting `~/vault/Kubernetes` with `--order makemd --format epub`:

1. `vault.find_vault_root()` walks up from `Kubernetes/` to find `.obsidian`.
2. `vault.build_attachment_index()` indexes every non-markdown file in the
   vault by name.
3. `collector.build_tree()` builds a `SectionNode("Kubernetes")` with a
   `MakeMdOrderStrategy` reading `Kubernetes/.space/context.mdb` for child
   order, recursing into subfolders (e.g. `Workloads/Pods.md`).
4. For each note, `preprocess.default_pipeline()` strips frontmatter,
   resolves embeds/wikilinks, and fetches any remote images (via
   `curl_cffi` with a host-appropriate `Referer`).
5. `render.DocumentRenderer.render_nodes()` produces one HTML fragment per
   section/note, correctly demoted and nested.
6. `writer.epub.write_epub()` turns those fragments into XHTML chapters,
   embeds images as package items, and writes the `.epub`.
