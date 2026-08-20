"""Tests for obsidian2pdf.pagespec."""
from __future__ import annotations

import pytest

from obsidian2pdf.pagespec import PRESETS, resolve_size


def test_named_preset_a4():
    assert resolve_size("a4").css_size == "210.00mm 297.00mm"


def test_named_preset_kobo_libra_colour():
    assert resolve_size("kobo-libra-colour").css_size == "107.00mm 142.20mm"


def test_custom_px_dpi_spec():
    assert resolve_size("1264x1680@300").css_size == "107.02mm 142.24mm"


def test_custom_mm_spec():
    assert resolve_size("91x120mm").css_size == "91.00mm 120.00mm"


def test_zero_dpi_raises():
    with pytest.raises(ValueError, match="dpi must be positive"):
        resolve_size("100x100@0")


def test_unknown_spec_raises_with_presets_listed():
    with pytest.raises(ValueError) as exc_info:
        resolve_size("bogus")
    message = str(exc_info.value)
    assert "unknown page size 'bogus'" in message
    for name in PRESETS:
        assert name in message
