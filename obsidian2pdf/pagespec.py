"""Page geometry: named presets and custom size specs."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PageSpec:
    name: str
    width_mm: float
    height_mm: float
    base_font_pt: float = 10.0

    @property
    def css_size(self) -> str:
        return f"{self.width_mm:.2f}mm {self.height_mm:.2f}mm"


# Kobo presets are the device screens at 300 ppi, converted to millimetres.
PRESETS = {
    "a4": PageSpec("a4", 210.0, 297.0, 11.0),
    "a5": PageSpec("a5", 148.0, 210.0, 10.0),
    "kobo-libra-colour": PageSpec("kobo-libra-colour", 107.0, 142.2, 8.5),
    "kobo-clara": PageSpec("kobo-clara", 90.8, 122.6, 8.0),
}

_PX_SPEC = re.compile(r"^(\d+)x(\d+)@(\d+)$")
_MM_SPEC = re.compile(r"^(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm$")


def resolve_size(spec: str) -> PageSpec:
    """Resolve a preset name, 'WxH@DPI' (pixels), or 'WxHmm' into a PageSpec."""
    key = spec.strip().lower()
    if key in PRESETS:
        return PRESETS[key]
    m = _PX_SPEC.match(key)
    if m:
        w_px, h_px, dpi = (int(g) for g in m.groups())
        if dpi == 0:
            raise ValueError(f"dpi must be positive in size spec {spec!r}")
        return PageSpec(key, w_px / dpi * 25.4, h_px / dpi * 25.4)
    m = _MM_SPEC.match(key)
    if m:
        return PageSpec(key, float(m.group(1)), float(m.group(2)))
    raise ValueError(
        f"unknown page size {spec!r} — presets: {', '.join(sorted(PRESETS))}; "
        "custom: WxH@DPI (pixels) or WxHmm"
    )
