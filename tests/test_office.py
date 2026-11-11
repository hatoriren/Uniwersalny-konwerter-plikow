from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document
from odf.opendocument import load

from converter.converters.text import txt_to_docx, txt_to_odt
from converter.errors import DependencyError
from converter.libreoffice import convert_with_libreoffice, find_soffice
from converter.registry import ConversionRequest, execute

HAS_LIBREOFFICE = find_soffice() is not None


@pytest.fixture()
def office_files(tmp_path: Path) -> tuple[Path, Path]:
    text = tmp_path / "dokument.txt"
    text.write_text(
        "Raport testowy\n\nTo jest treść z polskimi znakami: ąćęłńóśźż.\n",
        encoding="utf-8",
    )
    docx_path = tmp_path / "dokument.docx"
    odt_path = tmp_path / "dokument.odt"
    txt_to_docx(text, docx_path)
    txt_to_odt(text, odt_path)
    return docx_path, odt_path


def test_missing_libreoffice_gives_clear_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("converter.libreoffice.find_soffice", lambda: None)

    with pytest.raises(DependencyError, match="LibreOffice"):
        convert_with_libreoffice(tmp_path / "plik.docx", tmp_path / "plik.pdf")


@pytest.mark.skipif(not HAS_LIBREOFFICE, reason="LibreOffice nie jest zainstalowany")
@pytest.mark.parametrize(
    ("source_name", "target_format"),
    [
        ("dokument.docx", ".pdf"),
        ("dokument.docx", ".odt"),
        ("dokument.odt", ".pdf"),
        ("dokument.odt", ".docx"),
    ],
)
def test_libreoffice_conversions(
    office_files: tuple[Path, Path],
    tmp_path: Path,
    source_name: str,
    target_format: str,
) -> None:
    docx_path, odt_path = office_files
    source = docx_path if source_name.endswith(".docx") else odt_path
    output_dir = tmp_path / f"out-{target_format[1:]}"
    output_dir.mkdir()

    request = ConversionRequest(
        source=source,
        target_format=target_format,
        output_dir=output_dir,
    )
    result = execute(request)

    assert result.exists()
    assert result.stat().st_size > 0
    if target_format == ".pdf":
        assert result.read_bytes().startswith(b"%PDF")
    else:
        assert result.read_bytes().startswith(b"PK")
        if target_format == ".docx":
            assert Document(str(result)).paragraphs
        else:
            assert load(str(result)).text.childNodes
