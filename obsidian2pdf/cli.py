"""Command-line entry point: wires collector, pipeline, renderer, writer."""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import vault
from .collector.ordering import AlphabeticalOrderStrategy, MakeMdOrderStrategy
from .collector.tree import build_tree
from .pagespec import PRESETS, resolve_size
from .writer.epub import write_epub
from .writer.pdf import write_pdf
from .preprocess.pipeline import default_pipeline
from .preprocess.transforms import NoteContext
from .render.cover import cover_html
from .render.document import DocumentRenderer, build_document, stylesheet

ORDERINGS = {
    "alpha": AlphabeticalOrderStrategy,
    "makemd": MakeMdOrderStrategy,
}


_EXAMPLES = """\
examples:
  # A folder, as A4 PDF (the default)
  obsidian2pdf ~/vault/Docker

  # Kobo-ready PDF, respecting make.md's manual note order
  obsidian2pdf ~/vault/Kubernetes -s kobo-libra-colour --order makemd -o kubernetes.pdf

  # EPUB, dropping images/audio, no syntax highlighting, no cover
  obsidian2pdf ~/vault/Docker --format epub --ignore png,jpg,mp3 --no-highlight --no-cover -o docker.epub

  # EPUB with your own cover artwork instead of the generated title page
  obsidian2pdf ~/vault/Kubernetes --format epub --cover-image ~/art/cover.jpg -o kubernetes.epub

  # A single note instead of a folder
  obsidian2pdf ~/vault/Docker/Basic.md -o basic.pdf

  # Custom page size for a different e-reader (px@dpi or mm)
  obsidian2pdf ~/vault/Kubernetes -s "1072x1448@300" -v -o kubernetes-custom.pdf
"""


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="obsidian2pdf",
        description="Export an Obsidian note or folder to a single PDF or EPUB.",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", type=Path, help="path to a .md note or folder")
    parser.add_argument(
        "-o", "--output", type=Path,
        help="output file (default: <input name>.<format> next to the input)",
    )
    parser.add_argument(
        "-s", "--size", default="a4",
        help=f"page size: {', '.join(sorted(PRESETS))}, WxH@DPI, or WxHmm "
             "(default: a4)",
    )
    parser.add_argument(
        "--order", choices=sorted(ORDERINGS), default="alpha",
        help="child ordering per folder (default: alpha)",
    )
    parser.add_argument(
        "--ignore", default="", metavar="EXT[,EXT...]",
        help='media types to drop from the output, e.g. "png,mp3"',
    )
    parser.add_argument(
        "--no-cover", action="store_true", help="skip the cover page"
    )
    parser.add_argument(
        "--cover-image", type=Path, default=None, metavar="PATH",
        help="use this image as the EPUB's cover thumbnail instead of the "
             "generated one; ignored for --format pdf and with --no-cover",
    )
    parser.add_argument(
        "--no-highlight", action="store_true",
        help="disable syntax highlighting in code blocks",
    )
    parser.add_argument(
        "--format", choices=("pdf", "epub"), default="pdf",
        help="output format (default: pdf); --size has no effect on epub",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print progress info"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = args.input.expanduser().resolve()
    if not input_path.exists():
        print(f"error: {input_path} does not exist", file=sys.stderr)
        return 2
    try:
        page = resolve_size(args.size)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.cover_image is not None and not args.cover_image.is_file():
        print(f"error: {args.cover_image} does not exist", file=sys.stderr)
        return 2

    ignored = frozenset(
        ext.strip().lstrip(".").lower()
        for ext in args.ignore.split(",")
        if ext.strip()
    )
    vault_root = vault.find_vault_root(input_path)
    attachments = vault.build_attachment_index(vault_root)
    if args.verbose:
        print(f"vault root: {vault_root} ({len(attachments)} attachments)")

    try:
        tree = build_tree(input_path, ORDERINGS[args.order]())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output = args.output or input_path.parent / (input_path.stem + f".{args.format}")
    with tempfile.TemporaryDirectory(prefix="obsidian2pdf-") as cache:
        def make_context(note_path: Path) -> NoteContext:
            return NoteContext(
                note_path=note_path,
                vault_root=vault_root,
                attachments=attachments,
                ignored_exts=ignored,
                image_cache_dir=Path(cache),
            )

        highlight = not args.no_highlight
        renderer = DocumentRenderer(default_pipeline(), make_context, highlight)
        cover = "" if args.no_cover else cover_html(tree.title)

        if args.format == "epub":
            css = stylesheet(PRESETS["a4"], highlight)
            custom_cover_image = None
            if cover and args.cover_image is not None:
                custom_cover_image = (
                    args.cover_image.read_bytes(),
                    f"cover-image{args.cover_image.suffix}",
                )
            write_epub(tree, renderer, output, css, cover, custom_cover_image)
        else:
            body = renderer.render(tree)
            document = build_document(body, stylesheet(page, highlight), cover)
            write_pdf(document, output)

    for warning in renderer.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if args.verbose:
        print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
