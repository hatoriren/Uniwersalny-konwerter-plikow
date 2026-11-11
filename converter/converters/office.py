from __future__ import annotations

from pathlib import Path

from ..libreoffice import convert_with_libreoffice
from ..registry import converter


@converter(".docx", ".pdf")
def docx_to_pdf(source: Path, target: Path) -> Path:
    return convert_with_libreoffice(source, target)


@converter(".odt", ".pdf")
def odt_to_pdf(source: Path, target: Path) -> Path:
    return convert_with_libreoffice(source, target)


@converter(".docx", ".odt")
def docx_to_odt(source: Path, target: Path) -> Path:
    return convert_with_libreoffice(source, target)


@converter(".odt", ".docx")
def odt_to_docx(source: Path, target: Path) -> Path:
    return convert_with_libreoffice(source, target)
