# CLI reference

```
obsidian2pdf <input_path> [options]
```

`<input_path>` is a `.md` note or a folder. The vault root is found by
walking up from `<input_path>` until a directory containing `.obsidian` is
found; if none exists, embeds resolve relative to the input itself.

## Options

| Flag | Default | Description |
|---|---|---|
| `-o, --output PATH` | `<input_name>.<format>` next to the input | Output file path. |
| `-s, --size SIZE` | `a4` | Page size for PDF output: `a4`, `a5`, `kobo-libra-colour`, `kobo-clara`, or a custom `WxH@DPI` (pixels, e.g. `1264x1680@300`) / `WxHmm` (e.g. `91x120mm`). Always parsed and validated, even for `--format epub`, but has no visual effect there — EPUB is reflowable and has no fixed page. |
| `--format {pdf,epub}` | `pdf` | Output format. |
| `--order {alpha,makemd}` | `alpha` | Child ordering within each folder. `alpha` is a natural sort (`"2"` before `"10"`). `makemd` reads the make.md Obsidian plugin's manual drag-order from `<folder>/.space/context.mdb`, falling back to `alpha` for any folder with no such database. |
| `--ignore EXT[,EXT...]` | none | Comma-separated file extensions (dot optional, case-insensitive) whose embeds are silently dropped — no placeholder, no link, no warning. Applies to both `![[embed]]` and `![](url)` forms. |
| `--no-cover` | cover included | Skip the title/date cover page (or EPUB cover chapter) *and* the EPUB's registered cover-image thumbnail. |
| `--cover-image PATH` | none (generated) | Use this image file as the EPUB's registered cover-image (the thumbnail shown in library/shelf views, e.g. Kobo's home screen) instead of the generated title/date one. Media type is auto-detected from the file extension. Ignored for `--format pdf` and whenever `--no-cover` is also given. |
| `--no-highlight` | highlighting on | Disable Pygments syntax highlighting; code blocks render as plain monospace text. |
| `-v, --verbose` | off | Print the resolved vault root, attachment count, and the output path on success. |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success. |
| `1` | The input folder contains no markdown notes anywhere (including subfolders). |
| `2` | The input path doesn't exist, `--size` is not a valid preset/custom spec, or `--cover-image` points to a file that doesn't exist. |

Warnings (missing local images, failed remote fetches, etc.) print to
stderr prefixed with `warning:` regardless of `-v`, and do not affect the
exit code — the export still completes.

## Examples

Default export (A4, alphabetical order):
```bash
obsidian2pdf ~/vault/Docker
```

Kobo-ready PDF, respecting make.md's manual note order:
```bash
obsidian2pdf ~/vault/Kubernetes -s kobo-libra-colour --order makemd -o kubernetes.pdf
```

EPUB, dropping images and audio, no syntax highlighting, no cover page:
```bash
obsidian2pdf ~/vault/Docker --format epub --ignore png,jpg,mp3 --no-highlight --no-cover -o docker.epub
```

Single note instead of a folder:
```bash
obsidian2pdf ~/vault/Docker/Basic.md -o basic.pdf
```

Custom page size for a different e-reader:
```bash
obsidian2pdf ~/vault/Kubernetes -s "1072x1448@300" -v -o kubernetes-custom.pdf
```

EPUB with your own cover artwork instead of the generated title page:
```bash
obsidian2pdf ~/vault/Kubernetes --format epub --cover-image ~/art/k8s-cover.jpg -o kubernetes.epub
```
