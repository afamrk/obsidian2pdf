"""Tests for obsidian2pdf.render.cover."""
from __future__ import annotations

from datetime import date

from obsidian2pdf.render.cover import cover_html, cover_image


def test_cover_html_escapes_title():
    html = cover_html("Test <Title>")
    assert "<div class=\"cover-title\">Test &lt;Title&gt;</div>" in html


def test_cover_html_includes_todays_date():
    html = cover_html("Anything")
    assert f"{date.today():%B %d, %Y}" in html


def test_cover_html_includes_obsidian_subtitle():
    html = cover_html("Anything")
    assert '<div class="cover-subtitle">Obsidian</div>' in html


def test_cover_image_returns_valid_png():
    image_bytes = cover_image("Kubernetes")
    assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(image_bytes) > 0
