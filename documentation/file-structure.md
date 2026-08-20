# File structure

```
obsidian_export/
├── pyproject.toml              # package metadata, dependencies, entry point
├── README.md                   # user-facing install/usage
├── documentation/              # this folder
├── docs/superpowers/           # brainstorming specs + implementation plans
│   ├── specs/                  #   design docs, one per feature
│   └── plans/                  #   task-by-task implementation plans
├── obsidian2pdf/                # the package
│   ├── cli.py
│   ├── vault.py
│   ├── pagespec.py
│   ├── collector/
│   │   ├── ordering.py
│   │   └── tree.py
│   ├── preprocess/
│   │   ├── transforms.py
│   │   ├── pipeline.py
│   │   └── host_adapters.py
│   ├── render/
│   │   ├── document.py
│   │   ├── cover.py
│   │   └── theme.css
│   └── writer/
│       ├── pdf.py
│       └── epub.py
└── tests/                       # mirrors obsidian2pdf/'s layout 1:1
    ├── conftest.py
    ├── test_pagespec.py
    ├── test_vault.py
    ├── test_cli.py
    ├── collector/
    ├── preprocess/
    ├── render/
    └── writer/
```

## Module reference

Each entry: **what it does** / **depends on** / **used by**.

### `obsidian2pdf/cli.py`

The composition root. Parses arguments (`argparse`), resolves the vault
root and attachment index, builds the `DocumentTree`, wires a
`DocumentRenderer` with the preprocessing pipeline, and dispatches to
`write_pdf` or `write_epub` based on `--format`. Converts every failure
mode into a specific exit code (2 = bad input/args, 1 = empty folder, 0 =
success). The only module that imports from every other package.

- **Depends on:** `vault`, `pagespec`, `collector.ordering`, `collector.tree`,
  `preprocess.pipeline`, `preprocess.transforms`, `render.document`,
  `render.cover`, `writer.pdf`, `writer.epub`
- **Used by:** the `obsidian2pdf` console script (`pyproject.toml`
  `[project.scripts]`)

### `obsidian2pdf/vault.py`

`find_vault_root(path)` walks up from a path until it finds a directory
containing `.obsidian`, falling back to the starting directory if none
exists (so exports outside a vault still work). `build_attachment_index(root)`
maps every non-markdown filename in the vault to its absolute path, for
Obsidian-style vault-wide `![[name]]` resolution.

- **Depends on:** nothing in this project (stdlib `pathlib` only)
- **Used by:** `cli`, `preprocess.transforms` (via the index it builds)

### `obsidian2pdf/pagespec.py`

`PageSpec` is a frozen dataclass (`width_mm`, `height_mm`, `base_font_pt`).
`PRESETS` is a name → `PageSpec` registry (`a4`, `a5`, `kobo-libra-colour`,
`kobo-clara`). `resolve_size(spec)` looks up a preset name or parses a
custom `WxH@DPI` (pixels) or `WxHmm` string.

- **Depends on:** nothing in this project
- **Used by:** `cli`, `render.document` (for `@page` CSS and base font size)

### `obsidian2pdf/collector/ordering.py`

`OrderingStrategy` is a `Protocol` with one method: `order(folder, entries)
-> list[Path]`. `AlphabeticalOrderStrategy` natural-sorts (`"2"` before
`"10"`). `MakeMdOrderStrategy` reads `<folder>/.space/context.mdb` (a
SQLite database the make.md Obsidian plugin writes) — the `files` table's
row order is the plugin's manual drag-order — appending anything missing
from the table alphabetically, and falling back to alphabetical entirely
if the database is absent or unreadable.

- **Depends on:** stdlib `sqlite3`, `re`
- **Used by:** `collector.tree`, `cli` (selects the strategy from `--order`)

### `obsidian2pdf/collector/tree.py`

`NoteNode` (a file) and `SectionNode` (a folder, with an optional `intro`
note and a list of `children`) form a Composite tree. `build_tree(path,
strategy)` is the entry point: a file input returns a bare `NoteNode`; a
folder recurses, using the given `OrderingStrategy` for each level, and
raises `ValueError` if a folder contains no markdown notes anywhere.

- **Depends on:** `collector.ordering`
- **Used by:** `cli`, `render.document` (walks this tree), `writer.epub`
  (type-checks nodes while walking `render_nodes()`'s output)

### `obsidian2pdf/preprocess/transforms.py`

`NoteContext` is the per-note state threaded through every transform
(paths, the vault attachment index, ignored extensions, an image cache
directory, and a `warnings` list). Each `Transform` implements `apply(text,
ctx) -> str`:

| Transform | Job |
|---|---|
| `FrontmatterStripper` | removes a leading YAML block |
| `IgnoredMediaFilter` | drops `![[..]]`/`![](..)` embeds matching `--ignore` |
| `VideoEmbedToLink` | YouTube/Vimeo URLs → a styled link (can't embed video in a document) |
| `ImageEmbedResolver` | `![[img.png]]` → `![](file://...)`, vault-wide resolution |
| `NoteEmbedToLink` | remaining `![[..]]` (notes, blocks, audio) → a styled reference span |
| `WikilinkToText` | `[[Target\|alias]]` → styled plain text |
| `LocalMdImageResolver` | relative `![](path.png)` → absolute `file://` URI |
| `RemoteImageFetcher` | downloads `![](http...)` images via `curl_cffi`, verifying `Content-Type` |

- **Depends on:** `vault.IMAGE_EXTS`, `preprocess.host_adapters`, `curl_cffi`
- **Used by:** `preprocess.pipeline`

### `obsidian2pdf/preprocess/pipeline.py`

`Pipeline` masks fenced code blocks and inline code spans (replacing them
with placeholder tokens) before running any transform, then restores them
verbatim afterward — so Obsidian syntax inside a code sample is never
rewritten. `default_pipeline()` returns the transforms above in the exact
order that matters (e.g. ignored-media filtering before image resolution;
video classification before the generic image resolver).

- **Depends on:** `preprocess.transforms`
- **Used by:** `cli`, `render.document`

### `obsidian2pdf/preprocess/host_adapters.py`

`HostAdapter` is a `Protocol` (`matches(url)`, `fetch_target(url) ->
(url, referer)`). `ImgurAdapter` rewrites `i.imgur.com` direct links to
Imgur's `/download/<id>/` endpoint with a page-specific `Referer` (see
[design-decisions.md](design-decisions.md) for why). `GenericAdapter`
(always matches, used last) sets a parent-domain `Referer` for everything
else. `resolve_fetch_target(url)` picks the first matching adapter.

- **Depends on:** nothing in this project
- **Used by:** `preprocess.transforms.RemoteImageFetcher`

### `obsidian2pdf/render/document.py`

`DocumentRenderer.render_nodes(tree)` is the core: a recursive walk
producing `(node, depth, html_fragment)` tuples in document order.
`render(tree)` is `render_nodes()`'s fragments joined into one string, used
by the PDF path. `stylesheet(page_spec, highlight)` loads `theme.css`,
substitutes the page size/base font, and appends Pygments' generated CSS
unless `highlight=False`. `build_document(body, css, cover)` wraps
everything into a full HTML document for WeasyPrint.

- **Depends on:** `collector.tree`, `pagespec`, `preprocess.pipeline`,
  `preprocess.transforms`, `markdown`, `pygments`
- **Used by:** `cli`, `writer.epub` (consumes `render_nodes()` directly)

### `obsidian2pdf/render/cover.py`

`cover_html(title)` produces the title-page markup (title, an "Obsidian"
subtitle, and today's date) shared by both writers. `cover_image(title)`
renders the same three lines as a PNG (via Pillow) — the EPUB writer
registers this as the book's cover-image so library/shelf views (e.g.
Kobo's home screen) show a real thumbnail; see
[design-decisions.md](design-decisions.md). A user-supplied image
(`--cover-image`) bypasses `cover_image()` entirely and is used as-is.

- **Depends on:** `PIL` (Pillow)
- **Used by:** `cli` (`cover_html`), `writer.epub` (`cover_image`)

### `obsidian2pdf/render/theme.css`

The shared print/reflow stylesheet: page margins, heading sizes and
bookmark levels, code block styling, `.wikilink`/`.embed-ref`/`.missing-embed`
classes, and the cover page layout. `__PAGE_SIZE__` and `__BASE_FONT__` are
placeholder tokens substituted by `stylesheet()`.

- **Used by:** `render.document.stylesheet()` (for both PDF and EPUB — the
  `@page` rule is simply ignored by EPUB readers)

### `obsidian2pdf/writer/pdf.py`

One function: `write_pdf(html, out_path)` → `weasyprint.HTML(string=html).write_pdf(...)`.

- **Depends on:** `weasyprint`
- **Used by:** `cli`

### `obsidian2pdf/writer/epub.py`

`write_epub(tree, renderer, out_path, css, cover)` builds an `ebooklib`
`EpubBook`: one `EpubHtml` chapter per tree node (via `renderer.render_nodes()`),
an `_ImageEmbedder` that rewrites `file://` image sources into real
in-package binary items (deduplicated by source path), and a nested
`book.toc` built by recursing the same tree so the EPUB's table of contents
mirrors the folder structure. Each chapter's own internal headings are also
indexed (`_index_headings`/`_build_heading_tree`): unique anchor `id`s are
injected and a nested heading tree is merged into that chapter's TOC entry,
so navigation depth matches the PDF's automatic per-heading bookmarks. When
a cover is requested, also registers a real cover *image*
(`render.cover.cover_image`) via `book.set_cover(..., create_page=False)`
so library/shelf views show a thumbnail, not just a page inside the book.
Sets an explicit nav title ("Contents") to avoid duplicating the book's own
title — see [design-decisions.md](design-decisions.md) for all three fixes.

- **Depends on:** `collector.tree`, `render.cover.cover_image`,
  `render.document.DocumentRenderer`, `ebooklib`
- **Used by:** `cli`

## Test structure

`tests/` mirrors `obsidian2pdf/`'s package layout exactly — one test file
per source module (`tests/collector/test_ordering.py` tests
`obsidian2pdf/collector/ordering.py`, and so on). See
[testing.md](testing.md) for the fixture and mocking strategy.
