from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document
from odf.opendocument import load
from odf.teletype import extractText
from odf.text import P

from converter.converters.text import docx_to_txt, odt_to_txt, txt_to_docx, txt_to_odt
from converter.errors import ConversionFailedError


def test_txt_docx_txt_roundtrip(tmp_path: Path) -> None:
    source = tmp_path / " tekst.txt".strip()
    source.write_text(
        "Pierwszy akapit.\nDruga linia tego akapitu.\n\n"
        "Drugi akapit: zażółć gęślą jaźń.\n",
        encoding="utf-8",
    )
    docx_path = tmp_path / "tekst.docx"
    result_txt = tmp_path / "wynik.txt"

    txt_to_docx(source, docx_path)
    document = Document(str(docx_path))
    assert [paragraph.text for paragraph in document.paragraphs] == [
        "Pierwszy akapit.\nDruga linia tego akapitu.",
        "Drugi akapit: zażółć gęślą jaźń.",
    ]

    docx_to_txt(docx_path, result_txt)
    assert result_txt.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_txt_odt_txt_roundtrip(tmp_path: Path) -> None:
    source = tmp_path / "tekst.txt"
    source.write_text(
        "Akapit pierwszy.\nZ łamaniem wiersza.\n\nAkapit drugi: Łódź.\n",
        encoding="utf-8",
    )
    odt_path = tmp_path / "tekst.odt"
    result_txt = tmp_path / "wynik.txt"

    txt_to_odt(source, odt_path)
    document = load(str(odt_path))
    paragraphs = document.text.getElementsByType(P)
    assert [extractText(item) for item in paragraphs] == [
        "Akapit pierwszy.\nZ łamaniem wiersza.",
        "Akapit drugi: Łódź.",
    ]

    odt_to_txt(odt_path, result_txt)
    assert result_txt.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")


def test_txt_to_docx_reads_cp1250(tmp_path: Path) -> None:
    source = tmp_path / "stary.txt"
    source.write_bytes("Zażółć gęślą jaźń.\n".encode("cp1250"))
    target = tmp_path / "stary.docx"

    txt_to_docx(source, target)

    assert Document(str(target)).paragraphs[0].text == "Zażółć gęślą jaźń."


def test_docx_to_txt_includes_tables(tmp_path: Path) -> None:
    source = tmp_path / "tabela.docx"
    document = Document()
    document.add_paragraph("Lista osób:")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Imię"
    table.cell(0, 1).text = "Miasto"
    table.cell(1, 0).text = "Łucja"
    table.cell(1, 1).text = "Wrocław"
    document.save(str(source))

    target = tmp_path / "tabela.txt"
    docx_to_txt(source, target)

    content = target.read_text(encoding="utf-8")
    assert "Lista osób:" in content
    assert "Imię\tMiasto" in content
    assert "Łucja\tWrocław" in content


def test_docx_to_txt_rejects_corrupted_file(tmp_path: Path) -> None:
    source = tmp_path / "uszkodzony.docx"
    source.write_bytes(b"to nie jest plik docx")

    with pytest.raises(ConversionFailedError, match="DOCX"):
        docx_to_txt(source, tmp_path / "wynik.txt")


def test_odt_to_txt_rejects_corrupted_file(tmp_path: Path) -> None:
    source = tmp_path / "uszkodzony.odt"
    source.write_bytes(b"to nie jest plik odt")

    with pytest.raises(ConversionFailedError, match="ODT"):
        odt_to_txt(source, tmp_path / "wynik.txt")
