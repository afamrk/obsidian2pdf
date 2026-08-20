# Testing

## Running the suite

```bash
pip install -e ".[test]"
pytest tests/ -v
```

78 tests, no network access required, ~3 seconds. `pytest` and `pypdf` are
test-only dependencies (`[project.optional-dependencies] test` in
`pyproject.toml`) — not needed to run the tool itself.

## Structure

`tests/` mirrors `obsidian2pdf/`'s package layout 1:1 — every source module
has a matching test file:

```
tests/
├── conftest.py                     # the `vault` fixture (see below)
├── test_pagespec.py
├── test_vault.py
├── test_cli.py
├── collector/
│   ├── test_ordering.py
│   └── test_tree.py
├── preprocess/
│   ├── test_transforms.py
│   ├── test_pipeline.py
│   └── test_host_adapters.py
├── render/
│   ├── test_document.py
│   └── test_cover.py
└── writer/
    ├── test_pdf.py
    └── test_epub.py
```

## The `vault` fixture

`tests/conftest.py` defines a function-scoped `vault` fixture that builds a
small, deterministic Obsidian vault into pytest's `tmp_path` for every test
that requests it:

```
tmp_path/vault/
├── .obsidian/                      # empty — just the vault marker
└── Project/
    ├── Project.md                  # the folder note -> becomes section.intro
    ├── Alpha.md                    # frontmatter, subheading, image embed,
    │                                #   wikilink, note embed, ignored media,
    │                                #   fenced code containing embed-like text
    ├── Zeta.md                     # plain note, used as a link/embed target
    ├── attachments/
    │   └── pic.png                 # a real 1x1 PNG (valid image bytes)
    ├── .space/
    │   └── context.mdb             # real SQLite db, `files` table order:
    │                                #   Zeta, Alpha, Sub — NOT alphabetical
    └── Sub/
        └── Child.md
```

The deliberately non-alphabetical `context.mdb` row order exists so
`--order makemd` has something real to prove against the `alpha` default —
tests assert the make.md-ordered result differs from (and matches the
expected order of) the alphabetical one.

This is a *programmatic* fixture, not static files checked into git — it
was chosen over pointing tests at a real vault because the project's own
manual-testing vault moved paths twice during development. Rebuilding it
in Python each run means tests can never break because someone's personal
vault changed.

## Mocking the network

`RemoteImageFetcher` and `ImgurAdapter` make real HTTP requests in
production. Tests never touch the network — `curl_cffi`'s `requests.get`
(imported as `obsidian2pdf.preprocess.transforms.curl_requests`) is
monkeypatched with a small `FakeResponse` class:

```python
class FakeResponse:
    def __init__(self, status_code=200, headers=None, content=b""):
        ...
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RequestException(f"HTTP {self.status_code}")
```

This is deliberately expressive enough to reproduce the exact production
bug that motivated it: `tests/preprocess/test_transforms.py::test_remote_image_fetcher_imgur_html_200_regression`
mocks a response with `status_code=200` but `Content-Type: text/html`,
asserting the fetcher treats it as a failure rather than silently caching
an HTML page as if it were an image. See
[design-decisions.md](design-decisions.md) for the full story.

## What's mocked vs. what's real

| Layer | Approach | Why |
|---|---|---|
| `RemoteImageFetcher`, host adapters | Mocked HTTP | Deterministic, offline, and this is exactly where a real bug lived — see above. |
| `writer/pdf.py` (WeasyPrint) | Real library call | Fast, fully local. Inspecting real PDF output (`pypdf`: page geometry, bookmarks) is what actually catches page-size math errors. |
| `writer/epub.py` (ebooklib) | Real library call | Same reasoning — inspecting the real `.epub`'s `nav.xhtml` and embedded image bytes (`zipfile`) is what caught the TOC-duplication bug. |
| Everything else (collector, preprocessing transforms, rendering) | Real, in-process | No I/O beyond the synthetic fixture's own filesystem. |

## Adding a new test

1. If it needs vault content, request the `vault` fixture — it's
   auto-discovered by pytest from `conftest.py`, no import needed.
2. Put it in the file matching the source module it tests. A new source
   module gets a new test file in the equivalent location under `tests/`.
3. If it touches `RemoteImageFetcher` or a host adapter, mock
   `T.curl_requests.get` (see `test_transforms.py` for the pattern) —
   never let a test make a real network call.
4. Run `pytest tests/ -v` and confirm the new test plus the full suite
   both pass before committing.
