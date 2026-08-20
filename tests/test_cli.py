"""Tests for obsidian2pdf.cli."""
from __future__ import annotations

import zipfile

import pytest
from pypdf import PdfReader

from obsidian2pdf.cli import main, parse_args


def test_parse_args_defaults():
    args = parse_args(["some/path"])
    assert args.format == "pdf"
    assert args.size == "a4"
    assert args.order == "alpha"
    assert args.no_cover is False
    assert args.no_highlight is False
    assert args.cover_image is None


def test_parse_args_rejects_invalid_format():
    with pytest.raises(SystemExit):
        parse_args(["some/path", "--format", "bogus"])


def test_parse_args_rejects_invalid_order():
    with pytest.raises(SystemExit):
        parse_args(["some/path", "--order", "bogus"])


def test_main_missing_input_returns_2(capsys):
    code = main(["/nonexistent/path/xyz"])
    assert code == 2
    assert "does not exist" in capsys.readouterr().err


def test_main_bad_size_returns_2(vault, capsys):
    code = main([str(vault.project), "-s", "bogus"])
    assert code == 2
    assert "unknown page size" in capsys.readouterr().err


def test_main_empty_folder_returns_1(tmp_path, capsys):
    empty = tmp_path / "Empty"
    empty.mkdir()
    code = main([str(empty)])
    assert code == 1
    assert "no markdown notes found" in capsys.readouterr().err


def test_main_writes_pdf_by_default(vault, tmp_path):
    out = tmp_path / "out.pdf"
    code = main([str(vault.project), "-o", str(out)])
    assert code == 0
    assert out.is_file()
    reader = PdfReader(str(out))
    assert len(reader.pages) > 0


def test_main_writes_epub_with_makemd_order(vault, tmp_path):
    out = tmp_path / "out.epub"
    code = main([str(vault.project), "--format", "epub", "--order", "makemd", "-o", str(out)])
    assert code == 0
    with zipfile.ZipFile(out) as z:
        nav = z.read("EPUB/nav.xhtml").decode("utf-8")
    positions = [nav.index(f">{label}<") for label in ("Zeta", "Alpha", "Sub")]
    assert positions == sorted(positions)


def test_main_ignore_drops_media_type(vault, tmp_path):
    out = tmp_path / "out.epub"
    code = main([str(vault.project), "--format", "epub", "--ignore", "mp3", "-o", str(out)])
    assert code == 0
    with zipfile.ZipFile(out) as z:
        alpha_chapter = next(
            n for n in z.namelist() if n.startswith("EPUB/c") and n.endswith(".xhtml")
            and b"Alpha subheading" in z.read(n)
        )
        content = z.read(alpha_chapter).decode("utf-8")
    assert "sound.mp3" not in content


def test_main_no_cover(vault, tmp_path):
    out = tmp_path / "out.epub"
    code = main([str(vault.project), "--format", "epub", "--no-cover", "-o", str(out)])
    assert code == 0
    with zipfile.ZipFile(out) as z:
        nav = z.read("EPUB/nav.xhtml").decode("utf-8")
    assert "Cover</a>" not in nav


def test_main_no_highlight(vault, tmp_path):
    out_hl = tmp_path / "hl.epub"
    out_nohl = tmp_path / "nohl.epub"
    main([str(vault.project), "--format", "epub", "-o", str(out_hl)])
    main([str(vault.project), "--format", "epub", "--no-highlight", "-o", str(out_nohl)])
    assert out_nohl.stat().st_size < out_hl.stat().st_size


def test_main_bad_cover_image_returns_2(vault, capsys):
    code = main([str(vault.project), "--cover-image", "/nonexistent/cover.png"])
    assert code == 2
    assert "does not exist" in capsys.readouterr().err


def test_main_custom_cover_image_used_for_epub(vault, tmp_path):
    from PIL import Image

    custom = tmp_path / "custom.jpg"
    Image.new("RGB", (10, 10), "#123456").save(custom)
    out = tmp_path / "out.epub"

    code = main(
        [str(vault.project), "--format", "epub", "--cover-image", str(custom), "-o", str(out)]
    )
    assert code == 0
    with zipfile.ZipFile(out) as z:
        opf = z.read("EPUB/content.opf").decode("utf-8")
        cover_item = next(
            line for line in opf.splitlines() if 'properties="cover-image"' in line
        )
        href = cover_item.split('href="')[1].split('"')[0]
        image_bytes = z.read(f"EPUB/{href}")
    assert href == "cover-image.jpg"
    assert image_bytes == custom.read_bytes()


def test_main_no_cover_ignores_cover_image(vault, tmp_path):
    from PIL import Image

    custom = tmp_path / "custom.jpg"
    Image.new("RGB", (10, 10), "#123456").save(custom)
    out = tmp_path / "out.epub"

    code = main(
        [
            str(vault.project), "--format", "epub", "--no-cover",
            "--cover-image", str(custom), "-o", str(out),
        ]
    )
    assert code == 0
    with zipfile.ZipFile(out) as z:
        opf = z.read("EPUB/content.opf").decode("utf-8")
    assert "cover-image" not in opf
