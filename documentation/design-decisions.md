# Design decisions

Significant choices made while building obsidian2pdf, with the reasoning
and trade-offs behind each. Ordered roughly by when they were made.

## Stack: Python + WeasyPrint over Pandoc or Puppeteer

**Decision:** Markdown → HTML → PDF entirely in Python via `python-markdown`
and WeasyPrint, rather than shelling out to Pandoc or driving headless
Chrome with Puppeteer.

**Why:** No external binaries to install (Pandoc needs a LaTeX toolchain
for good PDF output; Puppeteer downloads a full Chromium). Full CSS control
over exact page dimensions, which is the entire point of the project — the
Kobo Libra Colour preset needs pixel-accurate page geometry, not "close
enough."

**Trade-off accepted:** WeasyPrint's CSS support is good but not
Chrome-identical; some advanced layout CSS isn't available. Acceptable
since the document is intentionally simple (headings, paragraphs, code
blocks, images, tables).

## Folder export: file name → heading, one heading level per nesting depth

**Decision:** Exporting a folder merges every note into one document. Each
note's filename becomes a heading; headings already inside the note are
demoted one level per nesting depth from the export root.

**Why:** This is literally how the user described the desired output when
asked: "# header become file name, then all other header inside file
become subheader." It also means a note edited in Obsidian in isolation
still produces sensible headings when merged into a larger export — no
per-note authoring changes needed.

## Ordering: alphabetical by default, make.md order opt-in

**Decision:** `--order alpha` (natural sort) is the default; `--order
makemd` reads the make.md Obsidian plugin's manual drag-order from
`<folder>/.space/context.mdb`.

**Why it changed:** The first design made make.md order the default,
matching how the user's vault is actually organized day-to-day. The user
then explicitly asked for the reverse: "default ordering must be normal
ordering, we can provide other order through input args like make.md."
Alphabetical is predictable and needs no plugin-specific state; make.md
order is an opt-in for users who've curated a specific reading order.

**How make.md order was reverse-engineered:** make.md has no public
documentation of its on-disk format. The format was discovered by
inspecting the user's real vault's `.obsidian/plugins/make-md/` directory,
reordering a note in the actual Obsidian app, and diffing the vault's
file-modification timestamps before/after to find which file changed
(`<folder>/.space/context.mdb`, a SQLite database with a `files` table
whose *row order* — not a rank column — encodes the sidebar order). This
was verified against a live vault before being written into code, not
assumed from the plugin's source.

## Page size: A4 by default, Kobo preset opt-in

**Decision:** `--size` defaults to `a4`; `kobo-libra-colour` and other
device presets are selectable but not default.

**Why it changed:** The project's original premise was Kobo-first
("compatible with Kobo Libra Colour"), so the Kobo preset was initially the
default. The user later asked for A4 as the default with other sizes
available via input — the tool is used for more than just Kobo exports, and
A4 is the more universally useful default for a general-purpose export.

## `--ignore`: CLI flag over an ignore file

**Decision:** `--ignore png,mp3` — a single flag listing extensions to drop
— rather than a `.gitignore`-style ignore file.

**Why:** Considered both; a per-run CLI flag was simpler for the actual
use case (skip noisy media types for a specific export) and needs no new
file format or discovery logic. An ignore file would only pay for itself
if there were a recurring need to exclude the *same* files across many
runs from the *same* folder — not the case here.

## Preprocessing: a Pipeline of single-purpose Transforms, not one big regex pass

**Decision:** Each Obsidian syntax (frontmatter, image embeds, wikilinks,
note embeds, video embeds, ignored media) is its own `Transform` class with
one `apply(text, ctx) -> str` method, run in a fixed order by a `Pipeline`
that masks fenced/inline code first.

**Why:** Explicitly chosen over a single large regex-and-replace function
during design: adding a new syntax (e.g. callouts, later) means adding one
new transform class, not editing a monolith. The code-masking step exists
specifically so a `![[embed.png]]`-looking string *inside* a code sample in
a note (e.g. documenting Obsidian syntax itself) is never mistaken for a
real embed.

## `writer/` package: PDF and EPUB as siblings sharing one render pass

**Decision:** `DocumentRenderer.render_nodes()` returns `(node, depth,
html_fragment)` tuples instead of only a joined string; `render()` (used by
PDF) is a thin wrapper around it. `writer/pdf.py` and `writer/epub.py` are
siblings in a `writer/` package, mirroring the project's existing
per-stage-package convention (`collector/`, `preprocess/`, `render/`).

**Why:** When EPUB support was added, the alternative was a parallel
rendering path duplicating the tree-walk/heading-demotion logic. Exposing
the walk as a flat, structured list let the EPUB writer reuse 100% of the
collection and preprocessing logic and only add packaging-specific code
(chapter files, image embedding, TOC nesting).

## Host-specific fetch handling: an Adapter, not special-cased inline

**Decision:** `preprocess/host_adapters.py` defines a `HostAdapter`
protocol; `ImgurAdapter` handles Imgur's quirks, `GenericAdapter` is the
always-matching fallback, and `resolve_fetch_target()` picks the first
match. `RemoteImageFetcher` calls this and knows nothing about specific
hosts.

**Why it was extracted:** Originally the Imgur-specific URL rewrite lived
directly inside `RemoteImageFetcher`. When asked "is it better to extract
that logic to other component," the answer was: not worth it for *one*
special case (YAGNI), but worth it the moment a second host-specific rule
was anticipated — and the user asked for the extraction, so it was done
immediately, mirroring the `OrderingStrategy` pattern already established
elsewhere in the codebase. Adding a second host's quirks later is a new
adapter class plus one line in `_ADAPTERS`, with zero changes to the
fetcher itself.

## Production bug: Imgur returns HTTP 200 with an HTML body for dead links

**What happened:** Early testing showed 24 "could not fetch" warnings for
images that should have worked. Direct investigation
(`curl_cffi.requests.get(url)`) showed `status_code=200` — but the response
body was a full Imgur HTML "page not found" document, not image bytes.
Plain `urllib` requests were separately found to get HTTP 429
(rate-limited) for the same URLs.

**Root cause:** `i.imgur.com` direct-links require (a) a browser-like
TLS/HTTP fingerprint to avoid being rate-limited at all, and (b) a
`Referer` header from the `imgur.com` parent domain to avoid being served
the generic "image removed" landing page *instead of a real 404* — so a
naive `response.status_code == 200` check cannot detect the failure.

**Fix, in two layers:**
1. `curl_cffi` with `impersonate="chrome"` replaces plain `urllib` (fixes
   the 429s).
2. `i.imgur.com` links get rewritten to `imgur.com/download/<id>/` with a
   `Referer: https://imgur.com/<id>` (fixes the fake-200 case) — and,
   defensively, `RemoteImageFetcher` now checks the response's
   `Content-Type` starts with `image/` before caching anything, so *any*
   host doing something similar fails loudly instead of silently caching
   an HTML page as if it were a picture.

**Regression coverage:** `tests/preprocess/test_transforms.py::test_remote_image_fetcher_imgur_html_200_regression`
mocks exactly this response shape (200 + `text/html`) and asserts it's
treated as a failure.

## Production bug: EPUB reader showed "Kubernetes" twice in the outline

**What happened:** A screenshot showed an EPUB reader's table-of-contents
panel listing "Kubernetes" as both the very first (unindented) entry and
again as the third entry, with "Cover" in between — reading as a broken,
duplicated header. The equivalent PDF bookmark tree had no such duplicate.

**Root cause investigation:** Direct inspection of the generated
`nav.xhtml` found the actual structure: `<h2>Kubernetes</h2>` (the nav
document's own heading) immediately followed by the real TOC's first entry,
`<a href="c1.xhtml">Kubernetes</a>` — the folder's own root chapter, which
is *also* named "Kubernetes." Reading `ebooklib`'s source
(`epub.py:_get_nav()`) confirmed the exact mechanism:
`content_title.text = item.title or self.book.title` — the `EpubNav` item
had no explicit `.title`, so it fell back to the book's title, which
happens to equal the root chapter's title for any folder export (both
derived from `tree.title`). PDF doesn't have this problem because the
cover page's title is a plain `<div>`, not a heading element, so it never
becomes a bookmark in the first place — only the folder's real `<h1>`
heading does, once.

**Fix:** `epub.EpubNav(title="Contents")` instead of the bare default,
so the nav's own heading reads "Contents" and is never coincidentally
identical to the book title.

**Regression coverage:** `tests/writer/test_epub.py::test_nav_heading_is_not_duplicated_book_title`.

## Production bug: EPUB navigation only showed one entry per file

**What happened:** After the above fix, the user reported the EPUB's
navigation was still thin: "only file heading are present." The PDF's
sidebar, by contrast, showed every internal heading in a note — down to
individual sub-sections like "kube-apiserver" — nested several levels deep.

**Root cause investigation:** Inspecting a chapter's raw XHTML
(`c2.xhtml`, the "Basic" note) confirmed the *content* was correct — every
internal heading (`<h3>`, `<h4>`, `<h5>`) was present and correctly
demoted, matching the PDF exactly. The gap was in navigation, not content:
WeasyPrint auto-generates a PDF bookmark for *every* heading tag in the
whole document via the `bookmark-level` CSS property on `h1`-`h6`
(`theme.css`), with no extra code required. The EPUB writer had no
equivalent — `write_epub()`'s `build()` created exactly one `nav.xhtml`
entry per tree node (file or folder), never looking inside a chapter's own
rendered HTML for its internal headings.

**Fix:** Each chapter's HTML is scanned for its own `<h1>`-`<h6>` tags
(skipping the first, which is the chapter's own synthetic title already
represented by its own TOC entry). Every subsequent heading gets a unique
injected anchor `id`, and a nested tree is built from the flat sequence of
(level, text, anchor) using a stack-based algorithm (the standard technique
for turning a flat list of heading levels into a nested outline). That
tree becomes nested `epub.Link(f"{chapter}#{anchor}", text, ...)` entries
merged into `book.toc` alongside the existing per-node section/child
entries — bringing EPUB navigation depth to parity with the PDF's
automatic bookmarks.

**Regression coverage:** `tests/writer/test_epub.py::test_internal_headings_get_nested_toc_entries`.

## Production bug: EPUB had no cover thumbnail in library/shelf views

**What happened:** The user reported "no cover for the epub," even though
`write_epub()` had always created a styled "Cover" title page as the
book's first chapter.

**Root cause investigation:** Inspecting the generated `content.opf`
showed the cover *page* (`cover.xhtml`) was present and correctly linked
in the spine, but nothing in `<metadata>` or the manifest identified any
item as the book's cover *image*. E-reader library/shelf views (Kobo's
home screen, Calibre's grid, etc.) don't open a book to find its cover —
they read a specific, separate mechanism: an EPUB3 manifest item with
`properties="cover-image"`, plus (for older reader compatibility) a
legacy `<meta name="cover" content="...">` pointing at an image item's id.
Neither existed; the "Cover" page was only ever visible once a reader
actually opened the book.

**Fix:** `render/cover.py` gained `cover_image(title) -> bytes`, rendering
the same title + date as `cover_html()` but as a PNG (via Pillow — already
an implicit dependency of WeasyPrint, now declared explicitly since it's
imported directly). WeasyPrint itself was considered first but ruled out:
this WeasyPrint version has no PNG export (`write_png` was removed;
`write_pdf` is the only output format available). `write_epub()` registers
the image with `ebooklib`'s `book.set_cover(file_name, image_bytes,
create_page=False)` — `create_page=False` matters because the default
`True` would add a *second* auto-generated cover page
(`EpubCoverHtml`, which defaults to the same `uid="cover"`/
`file_name="cover.xhtml"` as our own existing page), causing an id
collision with the styled cover page already in the spine.

**Regression coverage:** `tests/writer/test_epub.py::test_cover_image_is_registered_for_library_thumbnails`
and `test_no_cover_skips_cover_image_too`.

## Cover branding and a user-supplied cover image

**Decision:** The default cover (both `cover_html` and `cover_image`) shows
three lines — the folder/note title, an "Obsidian" subtitle, and today's
date — with larger fonts than the original title+date-only version.
`--cover-image PATH` lets a user supply their own artwork for the EPUB's
registered cover-image instead.

**Why "Obsidian" as a fixed subtitle, not configurable:** The export's
whole premise is "this came from an Obsidian vault" — a fixed brand line
is simple and matches every export's actual provenance; making it a flag
would be over-engineering for a single, always-true fact about the source.

**Why `--cover-image` only affects the *image*, not the cover *page*:** The
cover page (`cover_html`) is still just a text title page — a user's cover
artwork is exactly what library/shelf thumbnails need, but replacing the
in-book page too would be a bigger, separate change to `build_document`'s
page composition. Kept minimal: one new code path (skip `cover_image()`,
use the given bytes), reusing the same `book.set_cover(..., create_page=False)`
call already established for the generated case. Media type is left for
`ebooklib`'s own `guess_type()` to infer from the file extension (verified
against its source — `EpubItem.media_type` defaults to `""`, and packaging
auto-fills it when empty), so no separate extension→MIME mapping needed.

**Why no image processing (resize/reformat) of the user's file:** YAGNI —
nothing in the spec asked for it, and most readers handle arbitrary cover
image dimensions/formats fine. If a specific device turns out to need a
specific aspect ratio, that's a targeted follow-up, not a speculative one.

## Testing: synthetic fixture over the user's real vault

**Decision:** Automated tests build a small vault programmatically into
`tmp_path` via a `conftest.py` fixture, rather than pointing tests at the
user's actual test vault.

**Why:** The dedicated manual-testing vault moved twice during this
project (`~/learning/Obsidian/MyNotes` → `~/learning/Obsidian`), which
would have broken any test hard-coded to a real path. A programmatic
fixture is deterministic, portable, documents the exact make.md
`context.mdb` schema being relied on directly in Python, and can't drift.

**Why network calls are mocked, not skipped:** `RemoteImageFetcher` and
`ImgurAdapter` are exactly the code that had a real, subtle production bug
(above). Skipping network tests entirely would mean no automated coverage
of that exact failure mode. Mocking `curl_cffi`'s `requests.get` with
canned responses gives deterministic, offline coverage of success, HTTP
error, and the fake-200 case specifically.

**Why writer tests are not mocked:** `writer/pdf.py` and `writer/epub.py`
call the real WeasyPrint and `ebooklib` libraries and inspect the actual
output file (`pypdf`, `zipfile`). These are fast and fully local (no
network), and mocking them would test nothing — the page-geometry bug and
the nav-duplication bug were both the kind of thing only a real render/pack
step exposes.
