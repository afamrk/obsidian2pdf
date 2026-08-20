"""HTML -> PDF via WeasyPrint."""
from __future__ import annotations

from pathlib import Path

from weasyprint import HTML


def write_pdf(document_html: str, out_path: Path) -> None:
    HTML(string=document_html).write_pdf(str(out_path))
